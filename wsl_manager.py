"""Windows Subsystem for Linux のローカル管理画面。"""
import hashlib
import http.client
import os
import platform
import urllib.request
import webbrowser

import manager_theme as theme
import salome_image
import queue
import re
import subprocess
import tempfile
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def executable():
    if os.name != "nt":
        raise RuntimeError("このアプリは Windows 上で実行してください。")
    for directory in ("Sysnative", "System32"):
        path = Path(os.environ["SystemRoot"], directory, "wsl.exe")
        if path.is_file():
            return str(path)
    raise RuntimeError("wsl.exe が見つかりません。Windows の機能を確認してください。")


def decode(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif b"\0" in data:
        encoding = "utf-16-le"
    else:
        try:
            return data.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            encoding = "utf-16-le"
    return data.decode(encoding, errors="replace").strip()


def wsl(*args, input_data=None):
    result = subprocess.run([executable(), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, input=input_data,
                            stdin=subprocess.DEVNULL if input_data is None else None,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            env={**os.environ, "WSL_UTF8": "1"})
    if result.returncode:
        raise RuntimeError(decode(result.stderr) or decode(result.stdout)
                           or f"WSL 終了コード {result.returncode}")
    return decode(result.stdout)


def inventory():
    executable()
    import winreg
    # 登録情報は WSL の表示言語に依存しない。
    rows = []
    try:
        base = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                              r"Software\Microsoft\Windows\CurrentVersion\Lxss")
    except FileNotFoundError:
        return []
    with base:
        try:
            default = winreg.QueryValueEx(base, "DefaultDistribution")[0]
        except FileNotFoundError:
            default = ""
        for index in range(winreg.QueryInfoKey(base)[0]):
            key = winreg.EnumKey(base, index)
            try:
                with winreg.OpenKey(base, key) as distro:
                    name = winreg.QueryValueEx(distro, "DistributionName")[0]
                    version = winreg.QueryValueEx(distro, "Version")[0]
                    rows.append((name, version, key.lower() == default.lower()))
            except FileNotFoundError:
                continue
    running = {name.strip().casefold() for name in wsl("--list", "--running", "--quiet").splitlines()} if rows else set()
    return sorted([(name, version, primary, name.casefold() in running)
                   for name, version, primary in rows], key=lambda row: row[0].casefold())


def export_archive(name, target):
    target = Path(target)
    if target.exists():
        raise FileExistsError("同名のファイルがあります。別の保存名を指定してください。")
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        partial = Path(folder, "backup.tar")
        wsl("--export", name, str(partial))
        partial.rename(target)  # Windows の rename は既存ファイルを置換しない。


UBUNTU_BASE_URL = ("https://cdimage.ubuntu.com/ubuntu-base/releases/24.04/release/"
                   "ubuntu-base-24.04.5-base-amd64.tar.gz")
UBUNTU_BASE_SHA256 = "e77b6f10c2590cef872b33ee9f635a0e3fd1f57fb074c0e52b5c7f56147a0c86"


@dataclass(frozen=True)
class CaeProfile:
    default_name: str
    setup_script: str
    sif_source: bool = False
    supporting_scripts: tuple = ()
    resources: tuple = ()
    category: str = "その他"


OPENFOAM_WIZARD = "OpenFOAM（配布元・版を選択）"


@dataclass(frozen=True)
class OpenFoamEdition:
    repository: str
    package_pattern: str
    bundled_version: str
    prefix: str = ""


OPENFOAM_EDITIONS = {
    "OpenFOAM Foundation": OpenFoamEdition("https://dl.openfoam.org/ubuntu", r"openfoam([1-9][0-9]?)", "14"),
    "OpenFOAM Keysight": OpenFoamEdition("https://dl.openfoam.com/repos/deb", r"openfoam([0-9]{2}(?:06|12))-default", "2606", "v"),
}


def fetch_openfoam_versions(updates):
    for label, edition in OPENFOAM_EDITIONS.items():
        url = edition.repository + "/dists/noble/main/binary-amd64/Packages"
        request = urllib.request.Request(url, headers={"User-Agent": "OpenCAE-WSL-Manager/1"})
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                index = response.read().decode().replace("\r\n", "\n")
        except (OSError, http.client.HTTPException, UnicodeError):
            continue
        releases = set()
        for record in index.split("\n\n"):
            package = re.search("^Package: " + edition.package_pattern + "$", record, re.M)
            version = re.search(r"^Version: (\S+)$", record, re.M)
            if package and version:
                # Keysight released v2606; the noble metapackage still has a ~rc Debian revision.
                if "~" not in version[1] or package[0] == "Package: openfoam2606-default":
                    releases.add(package[1])
        if releases:
            updates.put((label, max(releases, key=int)))


CAE_PROFILES = {
    "OpenFOAM Foundation": CaeProfile("OpenFOAM-Foundation", "openfoam_foundation_setup.sh", category="流体解析",
                                            resources=("openfoam_latest.sh",)),
    "OpenFOAM Keysight": CaeProfile("OpenFOAM-Keysight", "openfoam_keysight_setup.sh", category="流体解析",
                                         resources=("openfoam_latest.sh",)),
    "Salome-Meca 2025.1": CaeProfile("Salome-Meca-2025", "salome_meca_setup.sh", category="構造・連成解析", sif_source=True),
    "OpenLB 1.9r0": CaeProfile("OpenLB-1.9r0", "openlb_setup.sh", category="流体解析"),
    "CalculiX": CaeProfile("CalculiX", "calculix_setup.sh", category="構造・連成解析"),
    "OpenCourant": CaeProfile("OpenCourant", "opencourant_setup.sh", category="構造・連成解析"),
    "OpenModelica": CaeProfile("OpenModelica", "openmodelica_setup.sh", category="構造・連成解析"),
    "FreeCAD": CaeProfile("FreeCAD", "freecad_setup.sh", category="CAD・メッシュ・可視化"),
    "TreeFOAM": CaeProfile("TreeFOAM", "treefoam_setup.sh", category="流体解析", supporting_scripts=("openfoam_setup.sh",)),
    "Netgen": CaeProfile("Netgen", "netgen_setup.sh", category="CAD・メッシュ・可視化"),
    "Gmsh": CaeProfile("Gmsh", "gmsh_setup.sh", category="CAD・メッシュ・可視化"),
    "ParaView": CaeProfile("ParaView", "paraview_setup.sh", category="CAD・メッシュ・可視化"),
    "Elmer FEM": CaeProfile("Elmer-FEM", "elmer_setup.sh", category="構造・連成解析"),
    "SU2": CaeProfile("SU2", "su2_setup.sh", category="流体解析"),
    "Code_Saturne": CaeProfile("Code-Saturne", "code_saturne_setup.sh", category="流体解析"),
    "MBDyn": CaeProfile("MBDyn", "mbdyn_setup.sh", category="構造・連成解析"),
}


ACCOUNT_FIELDS = (
    ("Linux ユーザー名", "cae", None),
    ("パスワード", "", "password"),
    ("パスワード（確認）", "", "password"),
)
RESERVED_USERS = set("root daemon bin sys sync games man lp mail news uucp proxy www-data "
                     "backup list irc _apt nobody systemd-network systemd-timesync messagebus syslog".split())


def validate_account(user, password, confirmation):
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or user in RESERVED_USERS:
        raise ValueError("予約名以外の Linux ユーザー名を指定してください（小文字英字か下線で始まる32文字以内）。")
    if not password or any(char in password for char in "\r\n\0"):
        raise ValueError("空文字・改行・NUL を含むパスワードは使用できません。")
    if password != confirmation:
        raise ValueError("確認用パスワードが一致しません。")


def configure_sudo(root, user, *, if_debian=False):
    script = Path(__file__).resolve().parent / "scripts" / "cae" / "configure_sudo.sh"
    options = ("--if-debian",) if if_debian else ()
    wsl(*root, "/bin/sh", "-s", "--", user, *options, input_data=script.read_text(encoding="utf-8").encode())


def create_linux_account(root, user, password, *, ubuntu_base=False):
    # useradd must succeed before setting a password. Never take over an existing account.
    if ubuntu_base:
        wsl(*root, "/usr/sbin/useradd", "-m", "-s", "/bin/bash", user)
    else:
        wsl(*root, "sh", "-ec",
            'if command -v useradd >/dev/null; then useradd -m "$1"; '
            'else adduser -D "$1"; fi', "sh", user)
    try:
        command = ("/usr/sbin/chpasswd", "--crypt-method", "YESCRYPT") if ubuntu_base else ("chpasswd",)
        wsl(*root, *command, input_data=f"{user}:{password}\n".encode("utf-8"))
    except RuntimeError:
        raise RuntimeError(f"「{user}」のパスワードを設定できませんでした。") from None
    configure_sudo(root, user, if_debian=not ubuntu_base)


def validate_install_folder(folder):
    if folder:
        dest = Path(folder)
        if not dest.is_dir() or any(dest.iterdir()):
            raise ValueError("保存先を指定する場合は空のフォルダーを選択してください。")


def register_archive(name, source, folder, version):
    validate_install_folder(folder)
    if folder:
        wsl("--import", name, str(Path(folder).resolve()), str(source), "--version", version)
    else:
        wsl("--install", "--from-file", str(source), "--name", name, "--version", version, "--no-launch")


def import_cae_base(name, folder, progress):
    arch = os.environ.get("PROCESSOR_ARCHITEW6432") or platform.machine()
    if arch.lower() not in ("amd64", "x86_64"):
        raise ValueError("この CAE 環境には x64 版 Windows が必要です。")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("登録名には半角英数字、ピリオド、下線、ハイフンを使用できます。")
    if name.casefold() in {row[0].casefold() for row in inventory()}:
        raise ValueError("同名の環境があります。未使用の登録名を指定してください。")
    validate_install_folder(folder)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp, "ubuntu.tar.gz")
        progress("Ubuntu 24.04 をダウンロード中…")
        digest = hashlib.sha256()
        with urllib.request.urlopen(UBUNTU_BASE_URL, timeout=90) as source, archive.open("wb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                output.write(chunk)
                digest.update(chunk)
        if digest.hexdigest() != UBUNTU_BASE_SHA256:
            raise ValueError("Ubuntu イメージの SHA-256 が一致しません。")
        progress("WSL 2 に Ubuntu を登録中…")
        register_archive(name, archive, folder, "2")


def discard_failed_environment(name, stage, error):
    try:
        wsl("--unregister", name)
    except (RuntimeError, OSError) as cleanup_error:
        raise RuntimeError(f"「{name}」の{stage}で失敗しました。{error}\n"
                           f"自動削除にも失敗しました。一覧を更新して「{name}」を確認してください。\n"
                           f"{cleanup_error}") from error
    raise RuntimeError(f"「{name}」の{stage}で失敗したため、この環境を削除しました。\n{error}") from error


def create_cae(selected, name, folder, progress, user, password, source="", *, openfoam_versions=None):
    if not selected:
        raise ValueError("ソフトを1つ以上選んでください。")
    wizard = OPENFOAM_WIZARD in selected
    profiles = [CAE_PROFILES[label] for label in selected if label != OPENFOAM_WIZARD]
    script_dir = Path(__file__).resolve().parent / "scripts" / "cae"
    steps = {}
    for profile in profiles:
        for filename in (*profile.supporting_scripts, profile.setup_script):
            steps.setdefault(filename, profile.default_name)
    resources = {filename for profile in profiles for filename in profile.resources}
    scripts = {filename: (script_dir / filename).read_text(encoding="utf-8").encode()
               for filename in (*steps, *resources, "resume.sh")}
    for label in selected:
        if label in OPENFOAM_EDITIONS:
            edition = OPENFOAM_EDITIONS[label]
            version = (openfoam_versions or {}).get(label, edition.bundled_version)
            script = CAE_PROFILES[label].setup_script
            scripts[script.replace("_setup.sh", ".version")] = (version + "\n").encode("ascii")
            steps[script] = f"{label} {edition.prefix}{version}"
    image = salome_image.prepare_image(source, progress) if any(p.sif_source for p in profiles) else None
    if wizard:
        progress("OpenFOAM の配布元と版をコンソールで選択してください")
        name = run_openfoam_wizard(user, password)
        if name is None:
            return "OpenFOAM 環境の作成をキャンセルしました"
        if not steps:
            return f"「{name}」の作成が完了しました"
    else:
        import_cae_base(name, folder, progress)
    root = ("-d", name, "-u", "root", "--exec")
    stage = "初期設定"
    try:
        for filename, content in scripts.items():
            wsl(*root, "tee", f"/root/{filename}", input_data=content)
        if image is not None:
            linux_path = wsl(*root, "wslpath", "-a", str(image))
            wsl(*root, "tee", "/root/salome-meca-source", input_data=(linux_path + "\n").encode())
        if not wizard:
            create_linux_account(root, user, password, ubuntu_base=True)
            wsl(*root, "tee", "/etc/wsl.conf", input_data=f"[user]\ndefault={user}\n".encode())
        wsl(*root, "tee", "/root/wsl-manager-user", input_data=(user + "\n").encode())
        wsl(*root, "tee", "/root/wsl-manager-plan", input_data=("\n".join(steps) + "\n").encode())
        for index, filename in enumerate(steps, 1):
            stage = filename
            progress(f"{name}（{index}/{len(steps)}） {steps[filename]} を導入中…")
            wsl(*root, "bash", "/root/resume.sh", filename)
        wsl("--terminate", name)
    except Exception as error:
        discard_failed_environment(name, stage, error)
    return f"「{name}」の作成が完了しました"


def run_openfoam_wizard(user, password):
    directory = Path(__file__).resolve().parent / "openfoam-installer"
    for filename in ("install-openfoam-wsl.bat", "install-openfoam-wsl.ps1"):
        if not (directory / filename).is_file():
            raise FileNotFoundError(f"同梱ファイルが見つかりません: {directory / filename}")
    # Use native Windows tools even when Python is a 32-bit process.
    windows = Path(os.environ["SystemRoot"])
    system = windows / "Sysnative"
    if not (system / "cmd.exe").is_file():
        system = windows / "System32"
    # pushd also supports a distribution extracted to a UNC share. Expand its
    # path as quoted data with delayed expansion off, not as command text.
    command = ('cmd.exe /d /v:off /s /c "pushd "%WSL_MANAGER_INSTALLER_DIR%" '
               '&& install-openfoam-wsl.bat"')
    # The interactive installer needs its own console. Protect the hand-off with
    # current-user Windows DPAPI; its stdin must stay attached to that console.
    powershell = system / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    protect = ("$ErrorActionPreference='Stop'; "
               "[Console]::InputEncoding=[Text.UTF8Encoding]::new($false); "
               "$s=ConvertTo-SecureString -AsPlainText -Force -String ([Console]::In.ReadToEnd()); "
               "ConvertFrom-SecureString $s")
    protected = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", protect],
                               input=password.encode(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    if protected.returncode or not re.fullmatch(rb"[0-9a-fA-F]+", protected.stdout.strip()):
        raise RuntimeError("OpenFOAM インストーラー用の認証情報を保護できませんでした。")
    with tempfile.TemporaryDirectory() as tmp:
        result_file = Path(tmp, "distribution.txt")
        result = subprocess.run(command, executable=str(system / "cmd.exe"),
                                env={**os.environ, "WSL_MANAGER_INSTALLER_DIR": str(directory),
                                     "WSL_MANAGER_USER": user, "WSL_MANAGER_RESULT": str(result_file),
                                     "WSL_MANAGER_DPAPI": protected.stdout.strip().decode("ascii")},
                                creationflags=subprocess.CREATE_NEW_CONSOLE)
        if result.returncode == 2:
            return None
        if result.returncode:
            error_file = Path(tmp, "distribution.txt.error")
            if error_file.is_file():
                raise RuntimeError(error_file.read_text(encoding="utf-8-sig"))
            raise RuntimeError(f"OpenFOAM の導入に失敗しました（終了コード {result.returncode}）。")
        name = result_file.read_text(encoding="utf-8-sig").strip()
        if not re.fullmatch(r"OpenFOAM-(?:Foundation-[0-9]+|Keysight-v[0-9]+)(?:-[0-9]+)?", name):
            raise RuntimeError("OpenFOAM の登録名を確認できませんでした。")
        return name


class Manager:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.progress = queue.SimpleQueue()
        self.busy = False
        self.rows = []
        self.buttons = []
        self.selected_buttons = []
        self.release_updates = queue.SimpleQueue()
        self.available_versions = {label: e.bundled_version for label, e in OPENFOAM_EDITIONS.items()}
        self.displayed_versions = self.available_versions.copy()
        self.software = {label: tk.BooleanVar(root) for label in (OPENFOAM_WIZARD, *CAE_PROFILES)}
        self.status = tk.StringVar(root)
        self.choice_count = tk.StringVar(root)
        self.inventory_count = tk.StringVar(root, "一覧を取得中…")
        root.title("OpenCAE · WSL Manager")
        width = min(1090, root.winfo_screenwidth() - 40)
        height = min(750, root.winfo_screenheight() - 96)
        root.geometry(f"{max(730, width)}x{max(540, height)}")
        root.minsize(730, 540)
        self.family = theme.configure(root)
        theme.masthead(root)

        footer = tk.Frame(root, background=theme.WHITE, padx=24, pady=5)
        footer.pack(side="bottom", fill="x")
        self.activity = ttk.Progressbar(footer, length=55, mode="indeterminate")
        tk.Label(footer, textvariable=self.status, anchor="w", bg=theme.WHITE,
                 fg=theme.MUTED).pack(side="left", fill="x", expand=True)

        self.pages = ttk.Notebook(root)
        self.pages.pack(fill="both", expand=True, padx=22, pady=(14, 10))
        catalog = ttk.Frame(self.pages, padding=(5, 13, 5, 4))
        inventory_page = ttk.Frame(self.pages, padding=(5, 13, 5, 4))
        self.pages.add(catalog, text="CAE 環境の作成")
        self.pages.add(inventory_page, text="WSL 環境の管理")
        self.pages.enable_traversal()
        self.build_catalog(catalog)
        self.build_inventory(inventory_page)
        self.controls()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)
        self.refresh()
        threading.Thread(target=fetch_openfoam_versions, args=(self.release_updates,), daemon=True).start()

    def software_label(self, label):
        if label in OPENFOAM_EDITIONS:
            return f"{label} {OPENFOAM_EDITIONS[label].prefix}{self.displayed_versions[label]}"
        return label

    def build_catalog(self, page):
        ttk.Label(page, text="ソフトウェアを選択", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="新しい WSL 環境にまとめてインストールするソフトを選んでください。",
                  style="Hint.TLabel").pack(anchor="w", pady=(1, 12))
        actions = ttk.Frame(page, padding=(0, 10, 0, 0))
        actions.pack(side="bottom", fill="x")
        ttk.Label(actions, textvariable=self.choice_count).pack(side="left")
        self.create_button = self.button(actions, "CAE 環境を作成", self.create_cae_environment, primary=True, side="right")

        viewport = tk.Canvas(page, bg=theme.PAPER, highlightthickness=0, width=1, height=1)
        scroll = ttk.Scrollbar(page, command=viewport.yview)
        scroll.pack(side="right", fill="y")
        viewport.configure(yscrollcommand=scroll.set, yscrollincrement=16)
        viewport.pack(fill="both", expand=True)
        groups = ttk.Frame(viewport)
        window = viewport.create_window(0, 0, anchor="nw", window=groups)
        cards = {}
        self.checks = []
        for label, variable in self.software.items():
            category = "流体解析" if label == OPENFOAM_WIZARD else CAE_PROFILES[label].category
            if category not in cards:
                card = tk.Frame(groups, bg=theme.WHITE, highlightbackground=theme.LINE, highlightthickness=1)
                cards[category] = card
                bar = tk.Frame(card, bg=theme.WHITE)
                bar.pack(fill="x", padx=12, pady=(12, 10))
                tk.Frame(bar, width=4, bg=theme.TEAL).pack(side="left", fill="y", padx=(0, 9))
                tk.Label(bar, text=category, bg=theme.WHITE, fg=theme.INK,
                         font=(self.family, 12, "bold")).pack(side="left")
                ttk.Separator(card).pack(fill="x")
            check = ttk.Checkbutton(cards[category], text=self.software_label(label), variable=variable,
                                    style="Catalog.TCheckbutton", command=self.controls)
            check.pack(anchor="w", fill="x", padx=4, pady=1)
            self.checks.append(check)

        def reflow(event):
            # One, two or three columns according to the actual font and window size.
            minimum = max(card.winfo_reqwidth() for card in cards.values()) + 12
            columns = max(1, min(len(cards), event.width // minimum))
            viewport.itemconfigure(window, width=event.width)
            for col in range(len(cards)):
                groups.columnconfigure(col, weight=int(col < columns), uniform="cards" if col < columns else "")
            for index, card in enumerate(cards.values()):
                row, col = divmod(index, columns)
                card.grid(row=row, column=col, sticky="new", padx=(0, 9), pady=(0, 9))
        viewport.bind("<Configure>", reflow)
        groups.bind("<Configure>", lambda _: viewport.configure(scrollregion=viewport.bbox("all")))

        def wheel(event):
            if getattr(event, "num", None) in (4, 5):
                units = -3 if event.num == 4 else 3
            else:
                units = -max(1, abs(event.delta) // 120) * (1 if event.delta > 0 else -1) * 3
            if self.pages.select() == str(page) and viewport.yview() != (0.0, 1.0):
                viewport.yview_scroll(units, "units")
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind(sequence, wheel, add=True)

        def reveal(event):
            top = event.widget.winfo_rooty() - viewport.winfo_rooty()
            bottom = top + event.widget.winfo_height() - viewport.winfo_height()
            delta = min(top, 0) if top < 0 else max(bottom, 0)
            if delta:
                viewport.yview_moveto((viewport.canvasy(0) + delta) / max(1, groups.winfo_height()))
        for check in self.checks:
            check.bind("<FocusIn>", reveal)

    def build_inventory(self, page):
        heading = ttk.Frame(page)
        heading.pack(fill="x")
        ttk.Label(heading, text="WSL 環境", style="Title.TLabel").pack(side="left")
        self.button(heading, "更新", self.refresh, side="right")
        ttk.Label(page, textvariable=self.inventory_count, style="Hint.TLabel").pack(anchor="w", pady=(1, 10))
        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=(0, 12))
        self.button(actions, "WSL にディストリビューションを追加", self.install)
        self.button(actions, "インポート", self.import_distro)

        commands = ttk.Frame(page)
        commands.pack(side="bottom", fill="x", pady=(12, 0))
        for label, handler in (("選択した WSL を起動", self.terminal), ("停止", self.stop),
                               ("既定に設定", self.set_default), ("エクスポート", self.export),
                               ("選択した WSL を削除", self.remove)):
            button = ttk.Button(commands, text=label, command=handler,
                                style="Primary.TButton" if handler == self.terminal else "TButton")
            self.buttons.append(button)
            self.selected_buttons.append(button)
        def fit_commands(event):
            row = col = used = 0
            for button in self.selected_buttons:
                width = button.winfo_reqwidth() + 6
                if col and used + width > event.width:
                    row, col, used = row + 1, 0, 0
                button.grid(row=row, column=col, padx=(0, 6), pady=2, sticky="w")
                used += width
                col += 1
        commands.bind("<Configure>", fit_commands)
        for col, button in enumerate(self.selected_buttons):
            button.grid(row=0, column=col, padx=(0, 6))

        table = tk.Frame(page, bg=theme.WHITE, highlightbackground=theme.LINE, highlightthickness=1)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("name", "state", "version", "default"),
                                 height=3, show="headings", selectmode="browse")
        for col, label, width in zip(self.tree["columns"], ("登録名", "状態", "バージョン", "既定"),
                                     (310, 110, 115, 75)):
            self.tree.heading(col, text=label, anchor="w")
            self.tree.column(col, width=width, minwidth=50, anchor="w")
        scroll = ttk.Scrollbar(table, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.tag_configure("stripe", background="#f5f8f5")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.controls())
        self.tree.bind("<Double-1>", self.launch_row)
        self.tree.bind("<Return>", lambda _: self.terminal())

    def button(self, parent, text, command, primary=False, side="left"):
        button = ttk.Button(parent, text=text, command=command, style="Primary.TButton" if primary else "TButton")
        button.pack(side=side, padx=(0, 6))
        self.buttons.append(button)
        return button

    def selected(self):
        selected = self.tree.selection()
        return selected[0] if selected else ""

    def controls(self):
        count = sum(var.get() for var in self.software.values())
        self.choice_count.set(f"{count} 件選択中")
        for label, widget in zip(self.software, self.checks):
            if label in self.available_versions and not self.software[label].get():
                self.displayed_versions[label] = self.available_versions[label]
                widget.configure(text=self.software_label(label))
            widget.state(["disabled" if self.busy else "!disabled"])
        for button in self.buttons:
            disabled = self.busy or (button in self.selected_buttons and not self.selected())
            if button == self.create_button and count == 0:
                disabled = True
            button.state(["disabled" if disabled else "!disabled"])

    def run(self, label, work, done):
        if self.busy:
            return
        self.busy = True
        self.controls()
        self.status.set(label + "中…")
        self.activity.pack(side="right", padx=(10, 0))
        self.activity.start(18)
        def worker():
            try:
                value = work()
            except Exception as error:
                self.events.put((None, None, str(error)))
            else:
                self.events.put((done, value, None))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.release_updates.empty():
            label, version = self.release_updates.get()
            self.available_versions[label] = version
            self.controls()
        while not self.progress.empty():
            self.status.set(self.progress.get())
        try:
            done, value, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.activity.stop()
            self.activity.pack_forget()
            self.busy = False
            self.controls()
            if error is not None:
                self.status.set("操作に失敗しました")
                messagebox.showerror("WSL Manager", error, parent=self.root)
            else:
                done(value)
        self.root.after(80, self.poll)

    def refresh(self, notice=""):
        def display(rows):
            selected = self.selected()
            self.tree.delete(*self.tree.get_children())
            self.rows = rows
            total = len(rows)
            running_count = sum(bool(row[3]) for row in rows)
            self.inventory_count.set(f"登録 {total} 件   /   実行中 {running_count} 件" if total else "登録された WSL 環境はありません。")
            for index, (name, version, primary, running) in enumerate(rows):
                self.tree.insert("", "end", iid=name, values=(name, "実行中" if running else "停止中",
                                                            f"WSL {version}", "既定" if primary else "—"),
                                 tags=("stripe",) if index % 2 else ())
            if selected and self.tree.exists(selected):
                self.tree.selection_set(selected)
            self.controls()
            self.status.set((notice + "  ｜  " if notice else "") + f"{len(rows)} 件のディストリビューション")
        self.run("一覧を更新", inventory, display)

    def change(self, label, work):
        self.run(label, work, lambda _: self.refresh(label + "が完了しました"))

    def form(self, title, fields, submit, prompt=""):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        panel = ttk.Frame(dialog, padding=20)
        panel.pack()
        if prompt:
            ttk.Label(panel, text=prompt, wraplength=460).pack(anchor="w", pady=(0, 10))
        variables = []
        for label, initial, kind in fields:
            ttk.Label(panel, text=label).pack(anchor="w")
            line = ttk.Frame(panel)
            line.pack(fill="x", pady=(3, 12))
            var = tk.StringVar(value=initial)
            variables.append(var)
            if isinstance(kind, tuple):
                entry = ttk.Combobox(line, values=kind, textvariable=var, width=44,
                                     state="readonly" if initial in ("1", "2") else "normal")
            else:
                entry = ttk.Entry(line, textvariable=var, width=46, show="*" if kind == "password" else "")
            entry.pack(side="left", fill="x", expand=True)
            if len(variables) == 1:
                entry.focus_set()
            if kind == "sif":
                def pick_sif(v=var):
                    path = filedialog.askopenfilename(parent=dialog, filetypes=[("Salome-Meca SIF", "*.sif")])
                    if path:
                        v.set(path)
                ttk.Button(line, text="参照", command=pick_sif).pack(side="left")
                ttk.Button(line, text="公式配布ページ", command=lambda: webbrowser.open(salome_image.RELEASE_PAGE)).pack(side="left")
            if kind in ("file", "optional_directory"):
                def browse(v=var, k=kind):
                    path = (filedialog.askopenfilename(parent=dialog, filetypes=[("tar アーカイブ", "*.tar"), ("すべて", "*")])
                            if k == "file" else filedialog.askdirectory(parent=dialog))
                    if path:
                        v.set(path)
                ttk.Button(line, text="参照", command=browse).pack(side="left", padx=(5, 0))
        def accept(*_):
            try:
                values = [v.get() if field[2] == "password" else v.get().strip()
                          for v, field in zip(variables, fields)]
                if any(not value and field[2] != "optional_directory" for value, field in zip(values, fields)):
                    raise ValueError("必須項目を入力してください。")
                submit(*values)
            except ValueError as error:
                messagebox.showerror(title, str(error), parent=dialog)
                return
            dialog.destroy()
        footer = ttk.Frame(panel)
        footer.pack(fill="x")
        ttk.Button(footer, text=title, command=accept, style="Primary.TButton").pack(side="right")
        ttk.Button(footer, text="キャンセル", command=dialog.destroy).pack(side="right", padx=6)
        dialog.bind("<Return>", accept)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.grab_set()

    def create_cae_environment(self):
        selected = tuple(label for label, checked in self.software.items() if checked.get())
        if not selected:
            messagebox.showinfo("CAE 環境を作成", "ソフトを1つ以上選んでください。", parent=self.root)
            return
        versions = self.displayed_versions.copy()
        wizard = OPENFOAM_WIZARD in selected
        fields = []
        if not wizard:
            default = CAE_PROFILES[selected[0]].default_name if len(selected) == 1 else "CAE-Workspace"
            fields.extend([("新しい登録名", default, None), ("保存先（任意・空欄で WSL の既定）", "", "optional_directory")])
        fields.extend(ACCOUNT_FIELDS)
        if any(CAE_PROFILES[label].sif_source for label in selected if label != OPENFOAM_WIZARD):
            fields.append(("公式 .sif の直接リンク（HTTPS）または取得済みファイル", "", "sif"))

        def submit(*values):
            if wizard:
                name, folder = "", ""
            else:
                name, folder, *values = values
            user, password, confirmation, *source = values
            validate_account(user, password, confirmation)
            self.run("CAE 環境の作成",
                     lambda: create_cae(selected, name, folder, self.progress.put, user, password,
                                        source[0] if source else "", openfoam_versions=versions), self.refresh)

        prompt = "同じ WSL 環境に導入します。 " + "、".join(self.software_label(label) for label in selected)
        if wizard:
            prompt += "。続くコンソールで OpenFOAM の配布元と版を選択します。"
        self.form("CAE 環境を作成", fields, submit, prompt)

    def install(self):
        def submit(name, user, password, confirmation):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
                raise ValueError("配布元のディストリビューション名を入力してください。")
            validate_account(user, password, confirmation)
            def install_new():
                if name.casefold() in {row[0].casefold() for row in inventory()}:
                    raise ValueError("この登録名は既に使用されています。")
                wsl("--install", "-d", name, "--name", name, "--no-launch")
                try:
                    create_linux_account(("-d", name, "-u", "root", "--exec"), user, password)
                    wsl("--manage", name, "--set-default-user", user)
                except Exception as error:
                    discard_failed_environment(name, "初期設定", error)
            self.change("WSL にディストリビューションを追加", install_new)
        self.form("WSL にディストリビューションを追加", [("ディストリビューション名", "Ubuntu",
                                  ("Ubuntu", "Debian", "kali-linux", "openSUSE-Tumbleweed")), *ACCOUNT_FIELDS], submit,
                  "新規環境に作成する Linux ユーザーを指定してください。")

    def import_distro(self):
        def submit(name, source, folder, version):
            if not re.fullmatch(r"[\w][\w.-]*", name) or name.casefold() in {r[0].casefold() for r in self.rows}:
                raise ValueError("未使用の名前を指定してください。文字、数字、ピリオド、ハイフン、下線が使えます。")
            if not Path(source).is_file():
                raise ValueError("既存のアーカイブを指定してください。")
            validate_install_folder(folder)
            self.change("インポート", lambda: register_archive(name, source, folder, version))
        self.form("インポート", [("登録名", "", None), ("tar アーカイブ", "", "file"),
                                 ("保存先（任意・空欄で WSL の既定）", "", "optional_directory"),
                                 ("WSL バージョン", "2", ("1", "2"))], submit)

    def export(self):
        name = self.selected()
        target = filedialog.asksaveasfilename(parent=self.root, title="エクスポート先",
                                               initialfile=name + ".tar", defaultextension=".tar",
                                               filetypes=[("tar アーカイブ", "*.tar")], confirmoverwrite=False)
        if target:
            self.change("エクスポート", lambda: export_archive(name, target))

    def remove(self):
        name = self.selected()
        if self.busy or not name:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("WSL の削除")
        dialog.transient(self.root)
        panel = ttk.Frame(dialog, padding=18)
        panel.pack()
        ttk.Label(panel, text=f"「{name}」を削除しますか？", wraplength=420).pack(anchor="w")
        ttk.Label(panel, text="この環境の全データが削除されます。この操作は取り消せません。").pack(pady=(4, 16))
        actions = ttk.Frame(panel)
        actions.pack(anchor="e")

        def confirm():
            dialog.destroy()
            self.change(f"「{name}」の削除", lambda: wsl("--unregister", name))

        cancel = ttk.Button(actions, text="キャンセル", command=dialog.destroy)
        cancel.pack(side="left", padx=6)
        ttk.Button(actions, text="削除する", command=confirm, style="Danger.TButton").pack(side="left")
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.bind("<Return>", lambda _: dialog.destroy())
        dialog.wait_visibility()
        dialog.grab_set()
        cancel.focus_set()

    def launch_row(self, event):
        row = self.tree.identify_row(event.y)
        if row and self.tree.identify_region(event.x, event.y) == "cell":
            self.tree.selection_set(row)
            self.terminal()

    def terminal(self):
        name = self.selected()
        if self.busy or not name:
            return

        def launch():
            subprocess.Popen([executable(), "-d", name], creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.change(f"「{name}」のターミナル起動", launch)

    def stop(self):
        name = self.selected()
        if messagebox.askyesno("停止", f"「{name}」の実行中のプロセスを終了しますか？", parent=self.root):
            self.change("停止", lambda: wsl("--terminate", name))

    def set_default(self):
        name = self.selected()
        self.change("既定の変更", lambda: wsl("--set-default", name))

    def close(self):
        if self.busy:
            messagebox.showinfo("WSL Manager", "処理が完了してから閉じてください。", parent=self.root)
        else:
            self.root.destroy()


if __name__ == "__main__":
    window = tk.Tk()
    Manager(window)
    window.mainloop()

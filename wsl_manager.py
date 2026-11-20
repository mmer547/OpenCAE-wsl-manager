"""Windows Subsystem for Linux のローカル管理画面。"""
import hashlib
import os
import platform
import urllib.request
import webbrowser

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


OPENFOAM_WIZARD = "OpenFOAM（配布元・版を選択）"


CAE_PROFILES = {
    "OpenFOAM Foundation 12": CaeProfile("OpenFOAM-12", "openfoam_setup.sh"),
    "Salome-Meca 2025.1": CaeProfile("Salome-Meca-2025", "salome_meca_setup.sh", sif_source=True),
    "OpenLB 1.9r0": CaeProfile("OpenLB-1.9r0", "openlb_setup.sh"),
    "CalculiX": CaeProfile("CalculiX", "calculix_setup.sh"),
    "OpenCourant": CaeProfile("OpenCourant", "opencourant_setup.sh"),
    "OpenModelica": CaeProfile("OpenModelica", "openmodelica_setup.sh"),
    "FreeCAD": CaeProfile("FreeCAD", "freecad_setup.sh"),
    "TreeFOAM": CaeProfile("TreeFOAM", "treefoam_setup.sh", supporting_scripts=("openfoam_setup.sh",)),
    "Netgen": CaeProfile("Netgen", "netgen_setup.sh"),
    "Gmsh": CaeProfile("Gmsh", "gmsh_setup.sh"),
    "ParaView": CaeProfile("ParaView", "paraview_setup.sh"),
    "Elmer FEM": CaeProfile("Elmer-FEM", "elmer_setup.sh"),
    "SU2": CaeProfile("SU2", "su2_setup.sh"),
    "Code_Saturne": CaeProfile("Code-Saturne", "code_saturne_setup.sh"),
    "MBDyn": CaeProfile("MBDyn", "mbdyn_setup.sh"),
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


def create_linux_account(root, user, password):
    # useradd must succeed before setting a password. Never take over an existing account.
    wsl(*root, "sh", "-ec",
        'if command -v useradd >/dev/null; then useradd -m "$1"; '
        'else adduser -D "$1"; fi', "sh", user)
    try:
        wsl(*root, "chpasswd", input_data=f"{user}:{password}\n".encode("utf-8"))
    except RuntimeError:
        raise RuntimeError(f"パスワードを設定できませんでした。root で passwd {user} を実行してください。") from None


def import_cae_base(name, folder, progress):
    arch = os.environ.get("PROCESSOR_ARCHITEW6432") or platform.machine()
    if arch.lower() not in ("amd64", "x86_64"):
        raise ValueError("この CAE 環境には x64 版 Windows が必要です。")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("登録名には半角英数字、ピリオド、下線、ハイフンを使用できます。")
    if name.casefold() in {row[0].casefold() for row in inventory()}:
        raise ValueError("同名の環境があります。未使用の登録名を指定してください。")
    dest = Path(folder)
    if not dest.is_dir() or any(dest.iterdir()):
        raise ValueError("空の保存先フォルダーを選択してください。")
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
        wsl("--import", name, str(dest.resolve()), str(archive), "--version", "2")


def create_cae(selected, name, folder, progress, user, password, source=""):
    if not selected:
        raise ValueError("ソフトを1つ以上選んでください。")
    wizard = OPENFOAM_WIZARD in selected
    profiles = [CAE_PROFILES[label] for label in selected if label != OPENFOAM_WIZARD]
    script_dir = Path(__file__).resolve().parent / "scripts" / "cae"
    steps = {}
    for profile in profiles:
        for filename in (*profile.supporting_scripts, profile.setup_script):
            steps.setdefault(filename, profile.default_name)
    scripts = {filename: (script_dir / filename).read_text(encoding="utf-8").encode()
               for filename in (*steps, "resume.sh")}
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
            create_linux_account(root, user, password)
            wsl(*root, "usermod", "-s", "/bin/bash", user)
            wsl(*root, "tee", "/etc/wsl.conf", input_data=f"[user]\ndefault={user}\n".encode())
        wsl(*root, "tee", "/root/wsl-manager-user", input_data=(user + "\n").encode())
        wsl(*root, "tee", "/root/wsl-manager-plan", input_data=("\n".join(steps) + "\n").encode())
        for index, filename in enumerate(steps, 1):
            stage = filename
            progress(f"{name}（{index}/{len(steps)}） {steps[filename]} を導入中…")
            wsl(*root, "bash", "/root/resume.sh", filename)
        wsl("--terminate", name)
    except (RuntimeError, OSError) as error:
        raise RuntimeError(f"「{name}」の {stage} で停止しました。環境は登録済みです。一覧を更新してください。"
                           f"再開手順は README の「途中で失敗した場合」を参照してください。\n{error}") from error
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
        root.title("WSL Manager")
        root.geometry("920x740")
        root.minsize(740, 620)
        root.configure(bg="#f1f5f9")
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", font=("Yu Gothic UI", 10))
        style.configure("Treeview", rowheight=42, background="white", fieldbackground="white", borderwidth=0)
        style.configure("Treeview.Heading", background="#e7edf3", padding=8, relief="flat")
        style.map("Treeview", background=[("selected", "#d7f0ec")], foreground=[("selected", "#123c38")])
        header = tk.Frame(root, bg="#172b3a", padx=28, pady=15)
        header.pack(fill="x")
        tk.Label(header, text="▸_   WSL Manager", font=("Segoe UI", 18, "bold"),
                 fg="white", bg="#172b3a").pack(side="left")
        body = tk.Frame(root, bg="#f1f5f9", padx=26, pady=20)
        body.pack(fill="both", expand=True)
        title = tk.Frame(body, bg="#f1f5f9")
        title.pack(fill="x", pady=(0, 14))
        tk.Label(title, text="ディストリビューション", font=("Yu Gothic UI", 18, "bold"),
                 fg="#172b3a", bg="#f1f5f9").pack(side="left")
        self.buttons = []
        self.selected_buttons = []
        self.button(title, "更新", self.refresh, side="right")
        actions = tk.Frame(body, bg="#f1f5f9")
        actions.pack(fill="x", pady=(0, 12))
        choices = ttk.LabelFrame(body, text="インストールする CAE ソフト（複数選択可）", padding=6)
        choices.pack(before=actions, fill="x", pady=(0, 8))
        self.software = {}
        for index, label in enumerate((OPENFOAM_WIZARD, *CAE_PROFILES)):
            checked = tk.BooleanVar(value=False)
            self.software[label] = checked
            ttk.Checkbutton(choices, text=label, variable=checked).grid(
                row=index // 3, column=index % 3, sticky="w", padx=4)
        self.button(actions, "CAE 環境を作成", self.create_cae_environment, primary=True)
        self.button(actions, "インストール", self.install)
        self.button(actions, "インポート", self.import_distro)
        table = tk.Frame(body)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("name", "state", "version", "default"),
                                 show="headings", selectmode="browse")
        for col, label, width in zip(self.tree["columns"], ("名前", "状態", "バージョン", "既定"), (290, 105, 110, 80)):
            self.tree.heading(col, text=label, anchor="w")
            self.tree.column(col, width=width, minwidth=50, anchor="w")
        scroll = ttk.Scrollbar(table, command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.controls())
        commands = tk.Frame(body, bg="#f1f5f9")
        commands.pack(fill="x", pady=(12, 0))
        for label, handler in (("ターミナル", self.terminal), ("停止", self.stop),
                               ("既定に設定", self.set_default), ("エクスポート", self.export),
                               ("削除", self.remove)):
            self.selected_buttons.append(self.button(commands, label, handler))
        self.status = tk.StringVar(value="")
        tk.Label(root, textvariable=self.status, anchor="w", padx=26, pady=8,
                 bg="#e3ebeF", fg="#284451").pack(fill="x")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(80, self.poll)
        self.refresh()

    def button(self, parent, text, command, primary=False, side="left"):
        button = tk.Button(parent, text=text, command=command, relief="flat", padx=12, pady=6,
                           bg="#126b61" if primary else "#ffffff",
                           fg="white" if primary else "#273a48", font=("Yu Gothic UI", 10))
        button.pack(side=side, padx=(0, 6))
        self.buttons.append(button)
        return button

    def selected(self):
        selected = self.tree.selection()
        return selected[0] if selected else ""

    def controls(self):
        for button in self.buttons:
            disabled = self.busy or (button in self.selected_buttons and not self.selected())
            button.configure(state="disabled" if disabled else "normal")

    def run(self, label, work, done):
        if self.busy:
            return
        self.busy = True
        self.controls()
        self.status.set(label + "中…")
        def worker():
            try:
                value = work()
            except Exception as error:
                self.events.put((None, None, str(error)))
            else:
                self.events.put((done, value, None))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        while not self.progress.empty():
            self.status.set(self.progress.get())
        try:
            done, value, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
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
            for name, version, primary, running in rows:
                self.tree.insert("", "end", iid=name, values=(name, "実行中" if running else "停止中",
                                                            f"WSL {version}", "既定" if primary else ""))
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
            if kind in ("file", "directory"):
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
                if not all(values):
                    raise ValueError("すべての項目を入力してください。")
                submit(*values)
            except ValueError as error:
                messagebox.showerror(title, str(error), parent=dialog)
                return
            dialog.destroy()
        footer = ttk.Frame(panel)
        footer.pack(fill="x")
        ttk.Button(footer, text=title, command=accept).pack(side="right")
        ttk.Button(footer, text="キャンセル", command=dialog.destroy).pack(side="right", padx=6)
        dialog.bind("<Return>", accept)
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.grab_set()

    def create_cae_environment(self):
        selected = tuple(label for label, checked in self.software.items() if checked.get())
        if not selected:
            messagebox.showinfo("CAE 環境を作成", "ソフトを1つ以上選んでください。", parent=self.root)
            return
        wizard = OPENFOAM_WIZARD in selected
        fields = []
        if not wizard:
            default = CAE_PROFILES[selected[0]].default_name if len(selected) == 1 else "CAE-Workspace"
            fields.extend([("新しい登録名", default, None), ("保存先フォルダー（空）", "", "directory")])
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
                                        source[0] if source else ""), self.refresh)

        prompt = "同じ WSL 環境に導入します。 " + "、".join(selected)
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
                create_linux_account(("-d", name, "-u", "root", "--exec"), user, password)
                wsl("--manage", name, "--set-default-user", user)
            self.change("インストール", install_new)
        self.form("インストール", [("ディストリビューション名", "Ubuntu",
                                  ("Ubuntu", "Debian", "kali-linux", "openSUSE-Tumbleweed")), *ACCOUNT_FIELDS], submit,
                  "新規環境に作成する Linux ユーザーを指定してください。")

    def import_distro(self):
        def submit(name, source, folder, version):
            if not re.fullmatch(r"[\w][\w.-]*", name) or name.casefold() in {r[0].casefold() for r in self.rows}:
                raise ValueError("未使用の名前を指定してください。文字、数字、ピリオド、ハイフン、下線が使えます。")
            if not Path(source).is_file() or not Path(folder).is_dir() or any(Path(folder).iterdir()):
                raise ValueError("既存のアーカイブと、空の保存先フォルダーを指定してください。")
            self.change("インポート", lambda: wsl("--import", name, folder, source, "--version", version))
        self.form("インポート", [("登録名", "", None), ("tar アーカイブ", "", "file"),
                                 ("保存先フォルダー（空）", "", "directory"),
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
        def submit(confirmation):
            if confirmation != name:
                raise ValueError("入力した名前が一致しません。")
            self.change("削除", lambda: wsl("--unregister", name))
        self.form("削除", [("確認用のディストリビューション名", "", None)], submit,
                  f"「{name}」の登録と内部の全データを削除します。この操作は取り消せません。")

    def terminal(self):
        name = self.selected()
        def launch():
            subprocess.Popen([executable(), "-d", name], creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.change("ターミナルの起動", launch)

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

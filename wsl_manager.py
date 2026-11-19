"""Windows Subsystem for Linux のローカル管理画面。"""
import os
import queue
import re
import subprocess
import tempfile
import threading
import tkinter as tk
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


def wsl(*args):
    result = subprocess.run([executable(), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
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


class Manager:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.rows = []
        root.title("WSL Manager")
        root.geometry("920x580")
        root.minsize(740, 480)
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
        self.button(actions, "＋ インストール", self.install, primary=True)
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
                entry = ttk.Entry(line, textvariable=var, width=46)
            entry.pack(side="left", fill="x", expand=True)
            if len(variables) == 1:
                entry.focus_set()
            if kind in ("file", "directory"):
                def browse(v=var, k=kind):
                    path = (filedialog.askopenfilename(parent=dialog, filetypes=[("tar アーカイブ", "*.tar"), ("すべて", "*")])
                            if k == "file" else filedialog.askdirectory(parent=dialog))
                    if path:
                        v.set(path)
                ttk.Button(line, text="参照", command=browse).pack(side="left", padx=(5, 0))
        def accept(*_):
            try:
                values = [v.get().strip() for v in variables]
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

    def install(self):
        def submit(name):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
                raise ValueError("配布元のディストリビューション名を入力してください。")
            self.change("インストール", lambda: wsl("--install", "-d", name, "--no-launch"))
        self.form("インストール", [("ディストリビューション名", "Ubuntu",
                                  ("Ubuntu", "Debian", "kali-linux", "openSUSE-Tumbleweed"))], submit,
                  "一覧から選択するか、wsl --list --online に表示される名前を入力してください。")

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

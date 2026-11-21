"""OpenCAE マネージャーの配色、書体とヘッダー。"""
from pathlib import Path
import tkinter as tk
from tkinter import font, ttk

PAPER = "#f3f5f2"
WHITE = "#ffffff"
INK = "#14302e"
MUTED = "#4f6661"
LINE = "#d2dcd6"
TEAL = "#00675b"
MINT = "#d9efe3"


def configure(root):
    family = "Yu Gothic UI" if root.tk.call("tk", "windowingsystem") == "win32" else "Noto Sans CJK JP"
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        font.nametofont(name).configure(family=family, size=10)
    root.configure(background=PAPER)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=PAPER, foreground=INK, font=(family, 10),
                    bordercolor=LINE, focuscolor=TEAL)
    style.configure("TButton", padding=(11, 7), background=WHITE, borderwidth=1,
                    relief="flat", lightcolor=WHITE, darkcolor=WHITE, anchor="center")
    style.map("TButton", background=[("disabled", PAPER), ("pressed", LINE), ("active", "#e6eee9")],
              foreground=[("disabled", "#71817b")])
    for name, color, hover in (("Primary", TEAL, "#005347"), ("Danger", "#9d3934", "#812e2a")):
        style.configure(name + ".TButton", background=color, foreground=WHITE,
                        bordercolor=color, lightcolor=color, darkcolor=color, focuscolor=WHITE)
        style.map(name + ".TButton", background=[("disabled", "#dce4df"), ("active", hover)],
                  foreground=[("disabled", "#62716c")],
                  bordercolor=[("disabled", LINE)], lightcolor=[("disabled", LINE)],
                  darkcolor=[("disabled", LINE)])
    style.configure("TNotebook", borderwidth=0, tabmargins=0, background=PAPER)
    style.configure("TNotebook.Tab", padding=(20, 8), font=(family, 10, "bold"),
                    background=PAPER, foreground=MUTED, borderwidth=0, focuscolor=TEAL)
    style.map("TNotebook.Tab", background=[("selected", INK), ("active", MINT)],
              foreground=[("selected", WHITE)], focuscolor=[("selected", WHITE)],
              padding=[("selected", (20, 8)), ("!selected", (20, 8))])
    style.configure("Catalog.TCheckbutton", padding=(8, 7), background=WHITE, foreground=INK,
                    indicatorcolor=WHITE, indicatormargin=(0, 0, 9, 0))
    style.map("Catalog.TCheckbutton", background=[("selected", MINT), ("active", "#edf5ef")],
              indicatorbackground=[("selected", TEAL)], indicatorforeground=[("selected", WHITE)],
              foreground=[("disabled", MUTED)])
    style.configure("Treeview", background=WHITE, fieldbackground=WHITE, rowheight=38, borderwidth=0)
    style.configure("Treeview.Heading", background="#e5ece6", padding=(10, 8),
                    relief="flat", font=(family, 10, "bold"))
    style.map("Treeview", background=[("selected", MINT)], foreground=[("selected", INK)])
    style.configure("TEntry", padding=5, fieldbackground=WHITE)
    style.configure("Title.TLabel", font=(family, 19, "bold"))
    style.configure("Hint.TLabel", foreground=MUTED)
    return family


def masthead(root):
    header = tk.Frame(root, bg=INK)
    header.pack(fill="x")
    title = tk.Frame(header, bg=INK)
    title.pack(side="left", padx=30, pady=14)
    tk.Label(title, text="OpenCAE", font=("Segoe UI", 26, "bold"), fg=WHITE,
             bg=INK, anchor="w").pack(fill="x")
    tk.Label(title, text="WSL Manager", font=("Segoe UI", 11), fg="#a9d9c5",
             bg=INK, anchor="w").pack(fill="x")

    image = tk.PhotoImage(master=root, file=Path(__file__).with_name("assets") / "airfoil-flow.png")
    art = tk.Label(header, image=image, background=INK, borderwidth=0, anchor="e", width=1)
    art.image = image
    art.pack(side="right", fill="both", expand=True)

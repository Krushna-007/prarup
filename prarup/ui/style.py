"""Colours and widget styles, in one place. The app is always light, so it
reads the same on Windows, Linux and a Mac in dark mode."""

import tkinter as tk
from tkinter import font, ttk

BACKGROUND = "#f7f6f3"
PANEL = "#ffffff"
INK = "#24211d"
MUTED = "#6b665e"
LINE = "#e2dfd8"
ACCENT = "#e8590c"
SELECTED = "#ffe8d9"
ERROR = "#c92a2a"
WARNING = "#a85d00"


def apply(root: tk.Tk) -> None:
    base = font.nametofont("TkDefaultFont")
    size = base.cget("size")
    root.configure(background=BACKGROUND)
    root.option_add("*Font", base)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BACKGROUND, foreground=INK, bordercolor=LINE)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("Bar.TFrame", background=PANEL)
    style.configure("TLabel", background=BACKGROUND, foreground=INK)
    style.configure("Panel.TLabel", background=PANEL)
    style.configure("Brand.TLabel", background=PANEL, font=(base.cget("family"), size + 3, "bold"))
    style.configure("File.TLabel", background=PANEL, foreground=MUTED)
    style.configure("Title.TLabel", font=(base.cget("family"), size + 2, "bold"))
    style.configure("Hint.TLabel", foreground=MUTED)
    style.configure("Problem.TLabel", foreground=ERROR, background="#fff0f0", padding=6)
    style.configure("Status.TLabel", foreground=MUTED, padding=(10, 4))

    style.configure("TButton", background="#efece6", foreground=INK, padding=(8, 3), relief="flat")
    style.map("TButton", background=[("disabled", BACKGROUND), ("active", SELECTED)],
              foreground=[("disabled", "#aaa59c")])
    style.configure("Accent.TButton", background=ACCENT, foreground="white")
    style.map("Accent.TButton", background=[("disabled", "#f3c4a8"), ("active", "#c94c09")],
              foreground=[("disabled", "white")])
    style.configure("Danger.TButton", foreground=ERROR)
    style.configure("TCheckbutton", background=PANEL, foreground=INK)
    style.map("TCheckbutton", background=[("active", PANEL)])

    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                    rowheight=int(size * 2.1) if size > 0 else 24, borderwidth=0)
    style.map("Treeview", background=[("selected", SELECTED)], foreground=[("selected", INK)])
    style.configure("Treeview.Heading", background=BACKGROUND, foreground=MUTED, relief="flat")
    style.configure("TNotebook", background=BACKGROUND, borderwidth=0)
    style.configure("TNotebook.Tab", background=BACKGROUND, foreground=MUTED, padding=(12, 4))
    style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", INK)])
    style.configure("TCombobox", fieldbackground=PANEL, foreground=INK)
    style.configure("TEntry", fieldbackground=PANEL, foreground=INK)


def text_box(parent, value: str = "", height: int = 4) -> tk.Text:
    """A plain multi-line text field, with its colours set so dark mode cannot change them."""
    box = tk.Text(parent, height=height, wrap="word", undo=True, background=PANEL, foreground=INK,
                  insertbackground=INK, selectbackground=SELECTED, selectforeground=INK,
                  relief="flat", highlightthickness=1, highlightbackground=LINE,
                  highlightcolor=ACCENT, padx=8, pady=6)
    box.insert("1.0", value)
    return box


def entry(parent, value: str = "") -> ttk.Entry:
    field = ttk.Entry(parent)
    field.insert(0, value)
    return field

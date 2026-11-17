"""The paper as a tagged list: TITLE, AUTH, ABS, KEY, H1, P, FIG 3, TAB 2, EQ, REF.
A row with a problem is red and starts with a warning sign."""

import re
from tkinter import ttk

from prarup.ui.style import ERROR, MUTED

FRONT = ["title", "authors", "abstract", "keywords"]


def plain(markdown: str, limit: int = 70) -> str:
    """One readable line: Markdown marks removed, maths kept."""
    text = re.sub(r"\{[#.][^}]*\}", "", markdown)          # pandoc attributes like {#fig:1}
    text = re.sub(r"\\([^A-Za-z])", r"\1", text)            # escapes like 1\. or \'
    text = re.sub(r"\*\*|__|`|\^", "", text)                # bold, code, superscript marks
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


class Outline(ttk.Frame):
    def __init__(self, parent, on_select):
        super().__init__(parent)
        self.on_select = on_select
        self.tree = ttk.Treeview(self, columns=("tag", "content"), show="headings",
                                 selectmode="browse")
        self.tree.heading("tag", text="Tag", anchor="w")
        self.tree.heading("content", text="Content", anchor="w")
        self.tree.column("tag", width=64, stretch=False)
        self.tree.column("content", width=260)
        self.tree.tag_configure("problem", foreground=ERROR)
        self.tree.tag_configure("empty", foreground=MUTED)
        scroll = ttk.Scrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected)

    def _selected(self, _event):
        if self.tree.selection():
            self.on_select(self.tree.selection()[0])

    def add(self, key, tag, text, problems):
        style = "problem" if problems else ("empty" if text.startswith("(") else "")
        mark = "⚠ " if problems else ""
        self.tree.insert("", "end", iid=key, values=(tag, mark + text), tags=(style,))

    def show(self, m, findings):
        """Refill the list from the manuscript, keeping the selected row."""
        problems = {}
        for f in findings:
            key = f.block_id or {"META-01": "title", "META-02": "authors", "META-03": "abstract",
                                 "META-04": "keywords"}.get(f.code)
            if key:
                problems.setdefault(key, []).append(f.message)

        selected = self.selected()
        self.tree.delete(*self.tree.get_children())
        authors = ", ".join(a.name for a in m.authors)
        self.add("title", "TITLE", plain(m.title) or "(no title)", problems.get("title"))
        self.add("authors", "AUTH", authors or "(no authors)", problems.get("authors"))
        self.add("abstract", "ABS", plain(m.abstract) or "(no abstract)", problems.get("abstract"))
        self.add("keywords", "KEY", m.keywords or "(no keywords)", problems.get("keywords"))
        figure = table = 0
        for b in m.blocks:
            if b.kind == "figure":
                figure += 1
                tag, text = f"FIG {figure}", plain(b.caption) or "(no caption)"
            elif b.kind == "table":
                table += 1
                tag, text = f"TAB {table}", plain(b.caption) or "(no caption)"
            elif b.kind == "heading":
                tag, text = f"H{b.level}", "   " * (b.level - 1) + plain(b.text)
            elif b.kind == "references":
                tag, text = "REF", f"{len(b.entries)} references"
            else:
                tag = {"para": "P", "equation": "EQ"}.get(b.kind, b.kind.upper())
                text = plain(b.text)
            self.add(b.id, tag, text, problems.get(b.id))
        if selected:
            self.select(selected)

    def selected(self):
        return self.tree.selection()[0] if self.tree.selection() else None

    def select(self, key):
        if self.tree.exists(key):
            self.tree.selection_set(key)
            self.tree.see(key)

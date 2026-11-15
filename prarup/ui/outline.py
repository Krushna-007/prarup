"""The paper as a tagged outline: TITLE, AUTH, ABS, H1, P, FIG 3, TAB 2, EQ, REF."""

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

FRONT = "front"           # item data for the front matter entries
TAG_COLOURS = {
    "TITLE": "#5f3dc4", "AUTH": "#5f3dc4", "ABS": "#5f3dc4", "KEY": "#5f3dc4",
    "H": "#1864ab", "P": "#6b665e", "FIG": "#2b8a3e", "TAB": "#0b7285",
    "EQ": "#862e9c", "REF": "#a61e4d", "LIST": "#6b665e", "QUOTE": "#6b665e",
    "CODE": "#6b665e", "RAW": "#c92a2a",
}


def _plain(markdown: str, limit: int = 70) -> str:
    """One readable line: Markdown markup dropped, maths ($\\frac{a}{b}$) kept."""
    text = re.sub(r"\{(?:#|\.|reference-type)[^}]*\}", "", markdown)    # pandoc attributes
    text = re.sub(r"\\([^A-Za-z])", r"\1", text)                       # Markdown escapes: 1\. -> 1.
    text = re.sub(r"\*\*|__|(?<!\w)[*_](?!\s)|`|^#+\s*|^>\s*", "", text, flags=re.M)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


class Outline(QTreeWidget):
    """Emits the id of the chosen block, or "front:title" and friends."""

    chosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Tag", "Content"])
        self.setRootIsDecorated(False)
        self.setColumnWidth(0, 78)
        self.setUniformRowHeights(True)
        self.setIndentation(0)
        self.currentItemChanged.connect(self._changed)
        self._items: dict = {}

    def _changed(self, current, _previous) -> None:
        if current is not None:
            self.chosen.emit(current.data(0, Qt.ItemDataRole.UserRole))

    def _add(self, tag: str, text: str, key: str, problems: list) -> None:
        item = QTreeWidgetItem([tag, ("⚠  " if problems else "") + text])
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        colour = TAG_COLOURS.get(re.sub(r"[\d\s]", "", tag), "#6b665e")
        item.setForeground(0, QBrush(QColor(colour)))
        font = item.font(0)
        font.setBold(True)
        item.setFont(0, font)
        if problems:
            item.setForeground(1, QBrush(QColor("#c92a2a")))
            item.setToolTip(1, "\n".join(problems))
        self.addTopLevelItem(item)
        self._items[key] = item

    def show_paper(self, m, findings: list) -> None:
        """Rebuild the outline, keeping the current selection if it still exists."""
        current = self.currentItem().data(0, Qt.ItemDataRole.UserRole) if self.currentItem() else None
        by_block: dict = {}
        front_problems: dict = {}
        for f in findings:
            if f.block_id:
                by_block.setdefault(f.block_id, []).append(f.message)
            elif f.code.startswith("META"):
                front_problems.setdefault(f.code, []).append(f.message)

        self.blockSignals(True)
        self.clear()
        self._items = {}
        self._add("TITLE", m.title or "(no title)", f"{FRONT}:title", front_problems.get("META-01", []))
        names = ", ".join(a.name for a in m.authors) or "(no authors)"
        self._add("AUTH", names, f"{FRONT}:authors", front_problems.get("META-02", []))
        self._add("ABS", _plain(m.abstract) or "(no abstract)", f"{FRONT}:abstract",
                  front_problems.get("META-03", []))
        self._add("KEY", m.keywords or "(no keywords)", f"{FRONT}:keywords",
                  front_problems.get("META-04", []))
        figure = table = 0
        for b in m.blocks:
            problems = by_block.get(b.id, [])
            if b.kind == "heading":
                indent = "    " * (b.level - 1)
                self._add(f"H{b.level}", indent + _plain(b.text), b.id, problems)
            elif b.kind == "figure":
                figure += 1
                self._add(f"FIG {figure}", _plain(b.caption) or "(no caption)", b.id, problems)
            elif b.kind == "table":
                table += 1
                self._add(f"TAB {table}", _plain(b.caption) or "(no caption)", b.id, problems)
            elif b.kind == "equation":
                self._add("EQ", _plain(b.text), b.id, problems)
            elif b.kind == "references":
                self._add("REF", f"{len(b.entries)} references", b.id, problems)
            else:
                self._add({"para": "P"}.get(b.kind, b.kind.upper()), _plain(b.text), b.id, problems)
        self.blockSignals(False)
        if current in self._items:
            self.setCurrentItem(self._items[current])

    def select(self, key: str) -> None:
        if key in self._items:
            self.setCurrentItem(self._items[key])
            self.scrollToItem(self._items[key])

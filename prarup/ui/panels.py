"""The tabs under the editor: Missing, Images, PDF checks, Figure fit, Notes."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QTabWidget

RED, AMBER, GREEN = "#c92a2a", "#a15c00", "#2b8a3e"


class Panels(QTabWidget):
    """Lists of problems. Clicking one with a block jumps to that block."""

    jump = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.missing = self._list("Missing")
        self.images = self._list("Images")
        self.checks = self._list("PDF checks")
        self.fit = self._list("Figure fit")
        self.notes = self._list("Notes")

    def _list(self, title: str) -> QListWidget:
        widget = QListWidget()
        widget.setWordWrap(True)
        widget.itemClicked.connect(self._clicked)
        self.addTab(widget, title)
        return widget

    def _clicked(self, item: QListWidgetItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self.jump.emit(key)

    @staticmethod
    def _add(widget, text: str, colour: str, key: str = "") -> None:
        item = QListWidgetItem(text)
        item.setForeground(QBrush(QColor(colour)))
        item.setData(Qt.ItemDataRole.UserRole, key)
        widget.addItem(item)

    def _title(self, widget, name: str, count: int) -> None:
        self.setTabText(self.indexOf(widget), f"{name} ({count})" if count else name)

    def show_findings(self, findings: list, reports: list) -> None:
        self.missing.clear()
        self.images.clear()
        problems = [f for f in findings if f.group != "Images"]
        for f in sorted(problems, key=lambda f: f.severity != "error"):
            key = f.block_id or ("front:" + {"META-01": "title", "META-02": "authors",
                                             "META-03": "abstract", "META-04": "keywords"}
                                 .get(f.code, "title"))
            self._add(self.missing, f"{'⛔' if f.severity == 'error' else '⚠'}  {f.code}  {f.message}",
                      RED if f.severity == "error" else AMBER, key)
        if not problems:
            self._add(self.missing, "✓  Nothing missing.", GREEN)
        self._title(self.missing, "Missing", len(problems))

        image_findings = [f for f in findings if f.group == "Images"]
        for f in sorted(image_findings, key=lambda f: f.severity != "error"):
            self._add(self.images, f"{'⛔' if f.severity == 'error' else '⚠'}  {f.code}  {f.message}",
                      RED if f.severity == "error" else AMBER, f.block_id)
        clean = [r for r in reports if not any(f.block_id == r.block_id for f in image_findings)]
        for r in clean:
            self._add(self.images, f"✓  Fig. {r.figure} ({Path(r.path).name}): {r.dpi:.0f} dpi, "
                      f"{r.verdict}", GREEN, r.block_id)
        if not reports:
            self._add(self.images, "No bitmap images to inspect (vector PDF figures need no dpi check).",
                      "#6b665e")
        self._title(self.images, "Images", len(image_findings))

    def show_checks(self, result) -> None:
        self.checks.clear()
        if result is None:
            return
        if not result.ok:
            self._add(self.checks, "⛔  The paper did not compile.", RED)
            self._add(self.checks, result.log, RED)
            self._title(self.checks, "PDF checks", 1)
            return
        for issue in result.issues:
            mark = "⛔" if issue.severity == "error" else "⚠"
            fix = "   [Fix PDF can repair this]" if issue.can_fix else ""
            self._add(self.checks, f"{mark}  {issue.code}  {issue.message}{fix}",
                      RED if issue.severity == "error" else AMBER)
        if not result.issues:
            self._add(self.checks, f"✓  All PDF checks passed ({result.pages} pages).", GREEN)
        self._title(self.checks, "PDF checks", len(result.issues))

    def show_fit(self, lines: list) -> None:
        self.fit.clear()
        for line in lines:
            self._add(self.fit, line, AMBER if "below" in line or "Still" in line else "#24221f")
        self.setCurrentWidget(self.fit)

    def show_notes(self, notes: list) -> None:
        self.notes.clear()
        for note in notes:
            self._add(self.notes, "•  " + note, "#24221f")
        self._title(self.notes, "Notes", len(notes))

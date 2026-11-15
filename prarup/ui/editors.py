"""One editor per kind of block. Each saves through the Project, which writes
manuscript.json at once, then emits `changed` so the window refreshes."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from prarup import pandoc
from prarup.models import Author

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.pdf)"


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("hint")
    label.setWordWrap(True)
    return label


class Editor(QWidget):
    changed = Signal(str)          # a short message for the status bar

    def __init__(self, project, block_id: str = "", findings: list = (), parent=None):
        super().__init__(parent)
        self.project, self.block_id = project, block_id
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(14, 12, 14, 12)
        problems = [f for f in findings if f.block_id == block_id] if block_id else list(findings)
        if problems:
            box = QFrame()
            box.setObjectName("problem")
            inner = QVBoxLayout(box)
            for f in problems:
                label = QLabel(("⛔ " if f.severity == "error" else "⚠ ") + f.message)
                label.setWordWrap(True)
                inner.addWidget(label)
            self.layout_.addWidget(box)

    def save(self) -> str:
        """Save what is typed. Returns a message if anything changed, else "".

        Never emits `changed` itself: the window calls this when moving to
        another block, and must not rebuild the editor while it is saving.
        """
        return ""

    def save_and_tell(self) -> None:
        message = self.save()
        self.changed.emit(message or "Nothing to save.")

    def _row(self, *widgets) -> QHBoxLayout:
        row = QHBoxLayout()
        for w in widgets:
            if w is None:
                row.addStretch()
            else:
                row.addWidget(w)
        return row

    def _block_actions(self, save=True) -> QHBoxLayout:
        """Save · Move up · Move down · Insert below · Delete, shared by block editors."""
        buttons = []
        if save:
            self.save_button = QPushButton("Save")
            self.save_button.clicked.connect(self.save_and_tell)
            buttons.append(self.save_button)
        up, down = QPushButton("↑ Move up"), QPushButton("↓ Move down")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        add_para, add_fig = QPushButton("+ Paragraph below"), QPushButton("+ Figure below")
        add_para.clicked.connect(lambda: self._insert("para"))
        add_fig.clicked.connect(lambda: self._insert("figure"))
        delete = QPushButton("Delete block")
        delete.setObjectName("danger")
        delete.clicked.connect(self._delete)
        return self._row(*buttons, up, down, add_para, add_fig, None, delete)

    def _move(self, step: int) -> None:
        self.project.move(self.block_id, step)
        self.changed.emit("Moved.")

    def _insert(self, kind: str) -> None:
        block = self.project.insert(self.block_id, kind, "New paragraph." if kind == "para" else "")
        self.changed.emit(f"Added a {'paragraph' if kind == 'para' else 'figure'}.|{block.id}")

    def _delete(self) -> None:
        self.project.delete(self.block_id)
        self.changed.emit("Deleted.")


# ---------------------------------------------------------------- front matter

class FrontEditor(Editor):
    def __init__(self, project, findings, focus: str = "title", parent=None):
        super().__init__(project, "", [f for f in findings if f.code.startswith("META")], parent)
        m = project.m
        self.layout_.addWidget(_title("Title, authors, abstract"))
        self.layout_.addWidget(_hint("Found in the paper. Correct anything that is wrong; "
                                     "what is here is what goes in the IEEE title block."))
        self.title = QLineEdit(m.title)
        self.authors = QTableWidget(0, 2)
        self.authors.setHorizontalHeaderLabels(["Name", "Affiliation"])
        self.authors.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.authors.verticalHeader().setVisible(False)
        for a in m.authors or [Author("")]:
            self._author_row(a.name, a.affiliation)
        add, remove = QPushButton("+ Author"), QPushButton("− Remove selected")
        add.clicked.connect(lambda: self._author_row("", ""))
        remove.clicked.connect(lambda: self.authors.removeRow(self.authors.currentRow())
                               if self.authors.rowCount() > 1 else None)
        self.abstract = QPlainTextEdit(m.abstract)
        self.keywords = QLineEdit(m.keywords)
        self.keywords.setPlaceholderText("e.g. federated learning, UAV, edge computing")
        for label, widget in [("Title", self.title), ("Authors", self.authors)]:
            self.layout_.addWidget(QLabel(label))
            self.layout_.addWidget(widget)
        self.layout_.addLayout(self._row(add, remove, None))
        self.layout_.addWidget(QLabel("Abstract"))
        self.layout_.addWidget(self.abstract, 1)
        self.layout_.addWidget(QLabel("Keywords (Index Terms)"))
        self.layout_.addWidget(self.keywords)
        save = QPushButton("Save")
        save.clicked.connect(self.save_and_tell)
        self.layout_.addLayout(self._row(save, None))
        {"title": self.title, "authors": self.authors, "abstract": self.abstract,
         "keywords": self.keywords}.get(focus, self.title).setFocus()

    def _author_row(self, name: str, affiliation: str) -> None:
        row = self.authors.rowCount()
        self.authors.insertRow(row)
        self.authors.setItem(row, 0, QTableWidgetItem(name))
        self.authors.setItem(row, 1, QTableWidgetItem(affiliation))

    def save(self) -> str:
        authors = []
        for row in range(self.authors.rowCount()):
            name = (self.authors.item(row, 0).text() if self.authors.item(row, 0) else "").strip()
            place = (self.authors.item(row, 1).text() if self.authors.item(row, 1) else "").strip()
            if name:
                authors.append(Author(name, place))
        m = self.project.m
        new = (self.title.text().strip(), authors, self.abstract.toPlainText().strip(),
               self.keywords.text().strip())
        if new == (m.title, m.authors, m.abstract, m.keywords):
            return ""
        self.project.set_front(*new)
        return "Title block saved."


# ---------------------------------------------------------------- text

class TextEditor(Editor):
    KINDS = [("Paragraph", "para"), ("Heading", "heading"), ("Quote", "quote")]

    def __init__(self, project, block, findings, parent=None):
        super().__init__(project, block.id, findings, parent)
        self.block = block
        name = {"heading": "Heading", "para": "Paragraph", "quote": "Quote",
                "list": "List", "code": "Code", "raw": "Raw LaTeX"}.get(block.kind, block.kind)
        self.layout_.addWidget(_title(name))
        if block.detected:
            note = QLabel(f"Detected: {block.detected}")
            note.setObjectName("detected")
            self.layout_.addWidget(note)
        self.kind = QComboBox()
        for label, kind in self.KINDS:
            self.kind.addItem(label, kind)
        self.level = QSpinBox()
        self.level.setRange(1, 3)
        self.level.setPrefix("Level ")
        self.level.setValue(max(1, block.level))
        self.retaggable = block.kind in [k for _, k in self.KINDS]
        if self.retaggable:
            self.kind.setCurrentIndex([k for _, k in self.KINDS].index(block.kind))
            self.layout_.addLayout(self._row(QLabel("This block is a"), self.kind, self.level, None))
        self.level.setVisible(block.kind == "heading")
        self.kind.currentIndexChanged.connect(
            lambda: self.level.setVisible(self.kind.currentData() == "heading"))
        self.text = QPlainTextEdit(block.text)
        self.layout_.addWidget(self.text, 1)
        self.layout_.addWidget(_hint("Markdown: *italic*, **bold**, $x^2$ for maths, [@key] to cite."))
        self.layout_.addLayout(self._block_actions())

    def save(self) -> str:
        text, changed = self.text.toPlainText(), False
        if self.retaggable and (self.kind.currentData() != self.block.kind or (
                self.block.kind == "heading" and self.level.value() != self.block.level)):
            self.project.set_kind(self.block_id, self.kind.currentData(), self.level.value())
            changed = True
        if text != self.block.text:
            self.project.set_text(self.block_id, text)
            changed = True
        return "Saved." if changed else ""


class EquationEditor(Editor):
    def __init__(self, project, block, findings, parent=None):
        super().__init__(project, block.id, findings, parent)
        self.layout_.addWidget(_title("Equation"))
        if block.detected:
            note = QLabel(f"Detected: {block.detected}")
            note.setObjectName("detected")
            self.layout_.addWidget(note)
        self.layout_.addWidget(_hint("LaTeX maths, without $ signs. IEEE numbers it."))
        self.text = QPlainTextEdit(block.text)
        self.layout_.addWidget(self.text, 1)
        self.layout_.addLayout(self._block_actions())

    def save(self) -> str:
        text = self.text.toPlainText().strip()
        if text == self.project.m.find(self.block_id).text:
            return ""
        self.project.set_text(self.block_id, text)
        return "Equation saved."


# ---------------------------------------------------------------- figure

class FigureEditor(Editor):
    def __init__(self, project, block, findings, reports, number: int, parent=None):
        super().__init__(project, block.id, findings, parent)
        self.block = block
        self.layout_.addWidget(_title(f"Figure {number}"))
        if block.detected:
            note = QLabel(f"Detected: {block.detected}")
            note.setObjectName("detected")
            self.layout_.addWidget(note)

        strip = QWidget()
        cards = QHBoxLayout(strip)
        cards.setContentsMargins(0, 0, 0, 0)
        by_path = {r.path: r for r in reports}
        for index, path in enumerate(block.images):
            cards.addWidget(self._card(index, path, by_path.get(path)))
        if not block.images:
            empty = QLabel("No image. Add one below.")
            empty.setObjectName("hint")
            cards.addWidget(empty)
        cards.addStretch()
        scroll = QScrollArea()
        scroll.setWidget(strip)
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(330)
        self.layout_.addWidget(scroll)

        add = QPushButton("+ Add image…")
        add.clicked.connect(lambda: self._choose(len(block.images)))
        self.layout_.addLayout(self._row(add, None))
        self.layout_.addWidget(QLabel("Caption (IEEE adds “Fig. N.” itself)"))
        self.caption = QPlainTextEdit(block.caption)
        self.caption.setPlaceholderText("Missing: describe what the figure shows.")
        self.caption.setMaximumHeight(90)
        self.layout_.addWidget(self.caption)
        if block.fit_width:
            self.layout_.addWidget(_hint(f"Width set by the figure fitter: {block.fit_width}"
                                         + (", across both columns" if block.double else "")))
        self.layout_.addLayout(self._block_actions())

    def _card(self, index: int, path: str, report) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(250)
        box = QVBoxLayout(card)
        picture = QLabel()
        file = self.project.folder / path
        pixmap = QPixmap(str(file)) if file.is_file() else QPixmap()
        if not pixmap.isNull():
            picture.setPixmap(pixmap.scaled(226, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        else:
            picture.setText("missing" if not file.is_file() else Path(path).suffix + " (no preview)")
            picture.setObjectName("hint")
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture.setMinimumHeight(150)
        box.addWidget(picture)
        lines = [Path(path).name]
        if report:
            lines.append(f"{report.width_px} × {report.height_px} px")
            if report.dpi:
                flag = "  ⚠" if report.dpi < 300 else ""
                lines.append(f"{report.dpi:.0f} dpi printed at {report.printed_inches:.1f} in{flag}")
            lines.append(f"AI: {report.verdict}")
            lines += [f"• {e.text}" for e in report.evidence]
            if report.ai_score is not None:
                lines.append(f"Classifier: {report.ai_score:.0%} likely AI")
            if report.ai_note:
                lines.append(report.ai_note)
            if report.duplicate_of:
                lines.append(f"⚠ same as {Path(report.duplicate_of).name}")
        info = QLabel("\n".join(lines))
        info.setWordWrap(True)
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(info)
        replace, remove = QPushButton("Replace…"), QPushButton("Remove")
        replace.clicked.connect(lambda: self._choose(index))
        remove.clicked.connect(lambda: self._remove(index))
        box.addLayout(self._row(replace, remove))
        return card

    def _choose(self, index: int) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Choose an image", "", IMAGE_FILTER)
        if file:
            self.set_image(Path(file), index)

    def set_image(self, file: Path, index: int) -> None:
        self.save()
        self.project.set_image(self.block_id, file, index)
        self.changed.emit(f"Image {'replaced' if index < len(self.block.images) else 'added'}.")

    def _remove(self, index: int) -> None:
        self.project.remove_image(self.block_id, index)
        self.changed.emit("Image removed.")

    def save(self) -> str:
        caption = self.caption.toPlainText().strip()
        if caption == self.block.caption:
            return ""
        self.project.set_caption(self.block_id, caption)
        return "Caption saved."


# ---------------------------------------------------------------- table

class TableEditor(Editor):
    def __init__(self, project, block, findings, number: int, parent=None):
        super().__init__(project, block.id, findings, parent)
        self.block = block
        self.layout_.addWidget(_title(f"Table {number}"))
        if block.detected:
            note = QLabel(f"Detected: {block.detected}")
            note.setObjectName("detected")
            self.layout_.addWidget(note)
        self.layout_.addWidget(QLabel("Caption (IEEE puts it above the table)"))
        self.caption = QPlainTextEdit(block.caption)
        self.caption.setPlaceholderText("Missing: say what the table shows.")
        self.caption.setMaximumHeight(70)
        self.layout_.addWidget(self.caption)
        self.cells = self._cells()
        width = max((len(r) for r in self.cells), default=0)
        self.grid = QTableWidget(len(self.cells), width)
        self.grid.horizontalHeader().setVisible(False)
        for r, row in enumerate(self.cells):
            for c, cell in enumerate(row):
                self.grid.setItem(r, c, QTableWidgetItem(pandoc.stringify(cell[4]).replace("\n", " ")))
        self.grid.resizeColumnsToContents()
        self.layout_.addWidget(_hint("Edit a cell by double-clicking it. Edited cells lose their "
                                     "bold or italic formatting."))
        self.layout_.addWidget(self.grid, 1)
        self.layout_.addLayout(self._block_actions())

    def _cells(self) -> list:
        if not self.block.node:
            return []
        _, _, _, head, bodies, foot = self.block.node[0]["c"]
        rows = list(head[1])
        for body in bodies:
            rows += body[2] + body[3]
        rows += foot[1]
        return [row[1] for row in rows]

    def save(self) -> str:
        touched = False
        for r, row in enumerate(self.cells):
            for c, cell in enumerate(row):
                item = self.grid.item(r, c)
                text = item.text() if item else ""
                if text != pandoc.stringify(cell[4]).replace("\n", " "):
                    cell[4] = [{"t": "Plain", "c": [{"t": "Str", "c": text}]}]
                    touched = True
        caption = self.caption.toPlainText().strip()
        if caption != self.block.caption:
            self.project.set_caption(self.block_id, caption)
            return "Table saved."
        if touched:
            self.project.save()
            return "Table saved."
        return ""


# ---------------------------------------------------------------- references

class ReferencesEditor(Editor):
    def __init__(self, project, block, findings, parent=None):
        super().__init__(project, block.id, findings, parent)
        self.block = block
        self.layout_.addWidget(_title(f"References ({len(block.entries)})"))
        if project.m.bibliography:
            self.layout_.addWidget(_hint(f"From {project.m.bibliography}. BibTeX formats them in "
                                         "the PDF; edit the .bib file to change them."))
        else:
            self.layout_.addWidget(_hint("One reference per line, in citation order."
                                         + (" Keep the [key] at the start of each line."
                                            if block.keys else "")))
        lines = [f"[{k}] {e}" if block.keys else e
                 for k, e in zip(block.keys or [""] * len(block.entries), block.entries)]
        self.text = QPlainTextEdit("\n".join(lines))
        self.text.setReadOnly(bool(project.m.bibliography))
        self.layout_.addWidget(self.text, 1)
        self.layout_.addLayout(self._block_actions(save=not project.m.bibliography))

    def save(self) -> str:
        if self.project.m.bibliography:
            return ""
        import re
        keys, entries = [], []
        for line in self.text.toPlainText().splitlines():
            if not line.strip():
                continue
            match = re.match(r"^\[([^\]]+)\]\s*(.*)$", line) if self.block.keys else None
            keys.append(match.group(1) if match else f"ref{len(entries) + 1}")
            entries.append(match.group(2) if match else line.strip())
        new_keys = keys if self.block.keys else []
        if (entries, new_keys) == (self.block.entries, self.block.keys):
            return ""
        self.block.entries, self.block.keys = entries, new_keys
        self.project.save()
        return "References saved."

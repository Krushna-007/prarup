"""The desktop window.

Deliberately thin. Every piece of real work already exists as a function
in checks.py, convert.py, render.py and compile.py; this file only calls
them and shows what comes back.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from prarup.checks import run_all_checks
from prarup.compile import compile_pdf
from prarup.convert import docx_to_tex
from prarup.document import document_from_latex
from prarup.fix import embed_fonts
from prarup.models import Author, Rules
from prarup.render import render


def format_issue(issue) -> str:
    """One line of text for the compliance list."""
    label = "ERROR" if issue.severity == "error" else "WARN "
    suffix = "    [can fix]" if issue.can_fix else ""
    return f"{label}   {issue.code}   {issue.message}{suffix}"


def build_paper(
    source: Path,
    out_dir: Path,
    template: str,
    rules: Rules,
    title: str = "",
    authors: list | None = None,
    abstract: str = "",
):
    """Run the whole pipeline. Returns (pdf_path, issues).

    Same sequence the command line uses, kept in one place so the window
    and the CLI cannot drift apart. A blank title falls back to the first
    heading in the document.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if source.suffix.lower() == ".docx":
        fragment = docx_to_tex(source, out_dir, standalone=False)
        document = document_from_latex(
            fragment.read_text(),
            title=title,
            authors=authors or [],
            abstract=abstract,
        )
        tex_path = out_dir / (source.stem + ".tex")
        tex_path.write_text(render(document, template=template))
    elif source.suffix.lower() == ".pdf":
        return source, run_all_checks(source, rules)
    else:
        tex_path = source

    pdf_path, log = compile_pdf(tex_path, out_dir)
    if not pdf_path.exists():
        raise RuntimeError(log or "compilation produced no PDF")

    return pdf_path, run_all_checks(pdf_path, rules)


class BuildWorker(QThread):
    """Runs the pipeline off the UI thread so the window stays responsive."""

    done = Signal(object, object)   # pdf_path, issues
    failed = Signal(str)

    def __init__(self, source: Path, out_dir: Path, template: str,
                 rules: Rules, title: str, authors: list, abstract: str):
        super().__init__()
        self.source = source
        self.out_dir = out_dir
        self.template = template
        self.rules = rules
        self.title = title
        self.authors = authors
        self.abstract = abstract

    def run(self) -> None:
        try:
            pdf_path, issues = build_paper(
                self.source, self.out_dir, self.template, self.rules,
                title=self.title, authors=self.authors, abstract=self.abstract,
            )
        except Exception as exc:              # noqa: BLE001 - shown to the user
            self.failed.emit(str(exc))
        else:
            self.done.emit(pdf_path, issues)


class MainWindow(QWidget):
    """Open a manuscript, build it, look at the result and the problems."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Prarup")
        self.resize(1480, 820)

        self.source: Path | None = None
        self.pdf_path: Path | None = None
        self.issues: list = []
        self.worker: BuildWorker | None = None

        self.open_button = QPushButton("Open…")
        self.template_box = QComboBox()
        self.template_box.addItem("IEEE Conference", "ieee")
        self.build_button = QPushButton("Build")
        self.build_button.setEnabled(False)
        self.status = QLabel("Open a .docx, .tex or .pdf to begin.")

        top = QHBoxLayout()
        top.addWidget(self.open_button)
        top.addWidget(QLabel("Template:"))
        top.addWidget(self.template_box)
        top.addWidget(self.build_button)
        top.addStretch()
        top.addWidget(self.status)

        # ---- metadata the source file cannot supply ----
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("leave blank to use the first heading")

        self.author_table = QTableWidget(0, 2)
        self.author_table.setHorizontalHeaderLabels(["Name", "Affiliation"])
        self.author_table.verticalHeader().setVisible(False)
        self.author_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.author_table.setMaximumHeight(150)
        self.add_author_row()

        add_author = QPushButton("+")
        remove_author = QPushButton("\u2212")
        for button in (add_author, remove_author):
            button.setMaximumWidth(36)
        add_author.clicked.connect(self.add_author_row)
        remove_author.clicked.connect(self.remove_author_row)

        author_buttons = QHBoxLayout()
        author_buttons.addStretch()
        author_buttons.addWidget(add_author)
        author_buttons.addWidget(remove_author)

        self.abstract_edit = QPlainTextEdit()
        self.abstract_edit.setPlaceholderText("optional")
        self.abstract_edit.setMaximumHeight(130)

        form = QFormLayout()
        # without this the fields size to their content and the title
        # clips rather than filling the panel
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("Title", self.title_edit)
        form.addRow("Authors", self.author_table)
        form.addRow("", author_buttons)
        form.addRow("Abstract", self.abstract_edit)

        # keeps the rows together at the top instead of spreading them
        # down the full height of the window
        metadata_layout = QVBoxLayout()
        metadata_layout.addLayout(form)
        metadata_layout.addStretch()

        self.metadata_panel = QWidget()
        self.metadata_panel.setLayout(metadata_layout)
        self.metadata_panel.setMinimumWidth(320)
        self.metadata_panel.setMaximumWidth(380)

        self.pdf_document = QPdfDocument(self)
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.pdf_document)
        self.pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        # without this the page sits small in the middle of a grey field
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        self.issue_list = QListWidget()
        # messages name a font and a file, so they are long. Without
        # wrapping they clip and the panel grows a horizontal scrollbar.
        self.issue_list.setWordWrap(True)
        self.fix_button = QPushButton("Fix what can be fixed")
        self.fix_button.setEnabled(False)

        right = QVBoxLayout()
        right.addWidget(QLabel("Compliance"))
        right.addWidget(self.issue_list)
        right.addWidget(self.fix_button)

        right_panel = QWidget()
        right_panel.setLayout(right)
        right_panel.setMinimumWidth(340)
        right_panel.setMaximumWidth(420)

        middle = QHBoxLayout()
        middle.addWidget(self.metadata_panel)
        middle.addWidget(self.pdf_view, stretch=1)
        middle.addWidget(right_panel)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addLayout(middle)

        self.open_button.clicked.connect(self.choose_file)
        self.build_button.clicked.connect(self.start_build)
        self.fix_button.clicked.connect(self.repair)

    # --------------------------------------------------------------- metadata

    def add_author_row(self) -> None:
        row = self.author_table.rowCount()
        self.author_table.insertRow(row)
        for column in (0, 1):
            self.author_table.setItem(row, column, QTableWidgetItem(""))

    def remove_author_row(self) -> None:
        """Remove the selected row, or the last one.

        Always leaves one row behind. With none there is no way to type an
        author back in.
        """
        if self.author_table.rowCount() <= 1:
            return
        row = self.author_table.currentRow()
        self.author_table.removeRow(row if row >= 0 else self.author_table.rowCount() - 1)

    def set_authors(self, pairs) -> None:
        """Fill the table. Used by tests and when loading a document."""
        self.author_table.setRowCount(0)
        for name, affiliation in pairs:
            row = self.author_table.rowCount()
            self.author_table.insertRow(row)
            self.author_table.setItem(row, 0, QTableWidgetItem(name))
            self.author_table.setItem(row, 1, QTableWidgetItem(affiliation))
        if self.author_table.rowCount() == 0:
            self.add_author_row()

    def collect_authors(self) -> list:
        """Read the table, skipping rows with no name.

        A blank row would render as an empty IEEEauthorblock, which shows
        up on the page as a gap under the title.
        """
        authors = []
        for row in range(self.author_table.rowCount()):
            name_item = self.author_table.item(row, 0)
            affiliation_item = self.author_table.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            if not name:
                continue
            affiliation = (affiliation_item.text() if affiliation_item else "").strip()
            authors.append(Author(name, affiliation))
        return authors

    # ---------------------------------------------------------------- actions

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open manuscript", "", "Manuscripts (*.docx *.tex *.pdf)"
        )
        if path:
            self.load(Path(path))

    def load(self, path: Path) -> None:
        self.source = path
        self.build_button.setEnabled(True)
        self.status.setText(f"Ready: {path.name}")

    def start_build(self) -> None:
        if self.source is None:
            return
        self.build_button.setEnabled(False)
        self.status.setText("Building…")

        self.worker = BuildWorker(
            self.source, self.source.parent / "build",
            self.template_box.currentData(), Rules(),
            title=self.title_edit.text().strip(),
            authors=self.collect_authors(),
            abstract=self.abstract_edit.toPlainText().strip(),
        )
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def repair(self) -> None:
        if self.pdf_path is None:
            return
        fixed = self.pdf_path.with_name(self.pdf_path.stem + "-fixed.pdf")
        try:
            embed_fonts(self.pdf_path, fixed)
        except Exception as exc:              # noqa: BLE001
            self.status.setText(f"Repair failed: {exc}")
            return
        # never trust the repair; re-check before saying anything
        self.on_done(fixed, run_all_checks(fixed, Rules()))

    # ---------------------------------------------------------------- results

    def on_done(self, pdf_path: Path, issues: list) -> None:
        self.pdf_path = Path(pdf_path)
        self.pdf_document.load(str(pdf_path))
        self.show_issues(issues)
        self.build_button.setEnabled(True)

    def on_failed(self, message: str) -> None:
        self.status.setText("Build failed")
        self.issue_list.clear()
        self.issue_list.addItem(QListWidgetItem(message))
        self.build_button.setEnabled(True)

    def show_issues(self, issues: list) -> None:
        self.issues = issues
        self.issue_list.clear()

        for issue in issues:
            item = QListWidgetItem(format_issue(issue))
            if issue.severity == "error":
                item.setForeground(Qt.GlobalColor.red)
            self.issue_list.addItem(item)

        errors = sum(1 for i in issues if i.severity == "error")
        warnings = len(issues) - errors
        if not issues:
            self.status.setText("All checks passed.")
        else:
            self.status.setText(f"{errors} error(s), {warnings} warning(s)")

        self.fix_button.setEnabled(any(i.can_fix for i in issues))


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

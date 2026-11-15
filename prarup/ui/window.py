"""The Prarup main window.

    toolbar   Open · Build · Fit figures · Fix PDF · AI classifier · Export
    left      the paper's outline, every block tagged
    middle    the editor for the chosen block, over the Missing / Images /
              PDF checks / Figure fit / Notes tabs
    right     the IEEE PDF, rebuilt a moment after each edit
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from prarup.checks import run_all_checks
from prarup.fit import describe
from prarup.fix import embed_fonts
from prarup.images import classifier_available
from prarup.models import Rules
from prarup.project import Project
from prarup.ui.editors import (
    EquationEditor, FigureEditor, FrontEditor, ReferencesEditor, TableEditor, TextEditor,
)
from prarup.ui.outline import FRONT, Outline
from prarup.ui.panels import Panels
from prarup.ui.worker import Worker

PRESETS = Path(__file__).parent.parent / "presets"
OPEN_FILTER = "Papers (*.docx *.tex *.zip);;Word (*.docx);;LaTeX (*.tex);;LaTeX project (*.zip)"
REBUILD_DELAY_MS = 1500


def rules_for(template: str = "ieee") -> Rules:
    preset = PRESETS / f"{template}.yaml"
    return Rules.load(preset) if preset.exists() else Rules()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Prarup")
        self.resize(1560, 920)
        self.setAcceptDrops(True)
        self.project: Project | None = None
        self.findings: list = []
        self.editor = None
        self.workers: list = []
        self.busy = False
        self.rebuild_pending = False
        self.rules = rules_for()
        self.last_notice = ""
        self.choose_fit = self._ask_fit         # replaced in tests

        self._toolbar()
        self.outline = Outline()
        self.outline.chosen.connect(self.show_block)
        self.panels = Panels()
        self.panels.jump.connect(self.outline.select)

        self.editor_area = QScrollArea()
        self.editor_area.setWidgetResizable(True)
        self.editor_area.setWidget(self._welcome())

        self.pdf = QPdfDocument(self)
        self.preview = QPdfView(self)
        self.preview.setDocument(self.pdf)
        self.preview.setPageMode(QPdfView.PageMode.MultiPage)
        self.preview.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        middle = QSplitter(Qt.Orientation.Vertical)
        middle.addWidget(self.editor_area)
        middle.addWidget(self.panels)
        middle.setSizes([560, 300])
        main = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(self.outline)
        main.addWidget(middle)
        main.addWidget(self.preview)
        main.setSizes([330, 640, 590])
        self.setCentralWidget(main)
        self.statusBar().showMessage("Open a Word or LaTeX paper to begin.")

        self.rebuild_timer = QTimer(self, singleShot=True, interval=REBUILD_DELAY_MS)
        self.rebuild_timer.timeout.connect(self.build)
        self._enable()

    # ------------------------------------------------------------ chrome

    def _toolbar(self) -> None:
        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)
        brand = QLabel("प्रारूप  Prarup")
        brand.setObjectName("brand")
        bar.addWidget(brand)
        self.paper_name = QLabel("")
        self.paper_name.setObjectName("paperName")

        def action(text, slot, shortcut=None, tip=""):
            act = QAction(text, self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.setToolTip(tip or text)
            bar.addAction(act)
            return act

        self.open_action = action("Open…", self.choose_file, "Ctrl+O", "Open a .docx, .tex or .zip paper")
        self.build_action = action("Build", self.build, "Ctrl+B", "Build the IEEE PDF and check it")
        bar.widgetForAction(self.build_action).setObjectName("primary")
        self.fit_action = action("Fit figures", self.fit, None,
                                 "Resize figures to fit their columns and the page limit")
        self.fix_action = action("Fix PDF", self.fix_pdf, None, "Embed missing fonts, then re-check")
        self.classify_action = action("AI classifier", self.toggle_classifier, None,
                                      "Also run the AI-image classifier on photo-like figures")
        self.classify_action.setCheckable(True)
        self.export_action = action("Export…", self.export, "Ctrl+E",
                                    "Save a submission zip: PDF, LaTeX, images, report")
        save = QAction("Save", self)
        save.setShortcut(QKeySequence("Ctrl+S"))
        save.triggered.connect(lambda: self.save_editor())
        self.addAction(save)
        bar.addSeparator()
        bar.addWidget(self.paper_name)

    def _welcome(self) -> QWidget:
        page = QWidget()
        box = QVBoxLayout(page)
        box.addStretch()
        for text, name in [("Open your paper", "sectionTitle"),
                           ("Word (.docx), LaTeX (.tex), or a LaTeX project as .zip. "
                            "You can also drop the file on this window.", "hint"),
                           ("Prarup reads it into an outline, lists what is missing, checks every "
                            "image, and builds the IEEE conference PDF on the right.", "hint")]:
            label = QLabel(text)
            label.setObjectName(name)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(label)
        button = QPushButton("Open a paper…")
        button.clicked.connect(self.choose_file)
        box.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        box.addStretch()
        return page

    def _enable(self) -> None:
        has = self.project is not None and not self.busy
        for act in (self.build_action, self.fit_action, self.export_action):
            act.setEnabled(has)
        self.fix_action.setEnabled(has and self.project.last_build is not None
                                   and self.project.last_build.ok
                                   and any(i.can_fix for i in self.project.last_build.issues))
        self.classify_action.setEnabled(has and classifier_available())
        self.open_action.setEnabled(not self.busy)

    def _run(self, job, done, message: str) -> None:
        """Run job() in the background; done(result) on success."""
        self.busy = True
        self._enable()
        self.statusBar().showMessage(message)
        worker = Worker(job, self)
        worker.done.connect(lambda result: self._finished(done, result))
        worker.failed.connect(self._failed)
        self.workers.append(worker)
        worker.finished.connect(lambda: self.workers.remove(worker) if worker in self.workers else None)
        worker.start()

    def _finished(self, done, result) -> None:
        self.busy = False
        done(result)
        self._enable()
        if self.rebuild_pending:
            self.rebuild_pending = False
            self.build()

    def _failed(self, message: str) -> None:
        self.busy = False
        self.rebuild_pending = False
        self._enable()
        self.statusBar().showMessage("Something went wrong. See the message.")
        self._notice("Prarup", message, QMessageBox.Icon.Warning)

    def _notice(self, title: str, text: str, icon=QMessageBox.Icon.Information) -> None:
        """A message that does not block the window."""
        box = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok, self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.open()
        self.last_notice = text

    # ------------------------------------------------------------ open

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a paper", "", OPEN_FILTER)
        if path:
            self.open_file(Path(path))

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.open_file(Path(urls[0].toLocalFile()))

    def open_file(self, path: Path) -> None:
        def job():
            project = Project.open(path)
            return project, project.findings(classify=self.classify_action.isChecked())
        self._run(job, self._opened, f"Reading {path.name}…")

    def _opened(self, result) -> None:
        self.project, self.findings = result
        self.paper_name.setText(f"{self.project.source.name}  ·  IEEE Conference")
        self.setWindowTitle(f"Prarup · {self.project.source.name}")
        self.pdf.close()
        self._refresh_views()
        self.panels.show_notes(self.project.m.notes)
        self.outline.select(f"{FRONT}:title")
        m = self.project.m
        self.statusBar().showMessage(
            f"Read {len(m.blocks)} blocks, {len(m.figures())} figures, {len(m.tables())} tables. "
            f"{len(self.findings)} things to look at. Building the PDF…")
        self.rebuild_pending = True

    # ------------------------------------------------------------ views

    def _refresh_views(self) -> None:
        self.outline.show_paper(self.project.m, self.findings)
        self.panels.show_findings(self.findings, self.project.reports)

    def show_block(self, key: str) -> None:
        if self.project is None or not key:
            return
        self.save_editor(quiet=True)
        m = self.project.m
        if key.startswith(f"{FRONT}:"):
            editor = FrontEditor(self.project, self.findings, key.split(":", 1)[1])
        else:
            block = m.find(key)
            if block is None:
                return
            if block.kind == "figure":
                editor = FigureEditor(self.project, block, self.findings, self.project.reports,
                                      m.figures().index(block) + 1)
            elif block.kind == "table":
                editor = TableEditor(self.project, block, self.findings, m.tables().index(block) + 1)
            elif block.kind == "equation":
                editor = EquationEditor(self.project, block, self.findings)
            elif block.kind == "references":
                editor = ReferencesEditor(self.project, block, self.findings)
            else:
                editor = TextEditor(self.project, block, self.findings)
        editor.changed.connect(self._edited)
        self.editor = editor
        self.editor_area.setWidget(editor)

    def save_editor(self, quiet: bool = False) -> None:
        """Save what is typed in the editor. Quietly: refresh the lists and
        schedule a rebuild, but leave the editor itself alone."""
        if self.editor is None:
            return
        message = self.editor.save()
        if message and quiet:
            self.findings = self.project.findings(classify=self.classify_action.isChecked())
            self._refresh_views()
            self.rebuild_timer.start()
        elif message:
            self._edited(message)

    def _edited(self, message: str) -> None:
        message, _, select = message.partition("|")
        self.findings = self.project.findings(classify=False)
        if self.classify_action.isChecked():
            self.findings = self.project.findings(classify=True)
        self._refresh_views()
        key = select or (self.editor.block_id if self.editor and self.editor.block_id
                         and self.project.m.find(self.editor.block_id) else "")
        if key:
            self.outline.select(key)
            self.show_block(key)
        self.statusBar().showMessage(f"{message} Rebuilding the PDF in a moment…")
        self.rebuild_timer.start()

    # ------------------------------------------------------------ build, fit, fix

    def build(self) -> None:
        if self.project is None:
            return
        if self.busy:
            self.rebuild_pending = True
            return
        self.save_editor(quiet=True)
        self._run(lambda: self.project.build(self.rules), self._built, "Building the IEEE PDF…")

    def _built(self, result) -> None:
        self.panels.show_checks(result)
        if result.ok:
            page = self.preview.pageNavigator().currentPage()
            self.pdf.load(str(result.pdf))
            if 0 < page < self.pdf.pageCount():
                self.preview.pageNavigator().jump(page, self.preview.pageNavigator().currentLocation())
            over = result.pages - self.rules.page_limit
            pages = f"{result.pages} pages" + (f", {over} over the {self.rules.page_limit}-page limit"
                                              if over > 0 else "")
            errors = sum(1 for i in result.issues if i.severity == "error")
            self.statusBar().showMessage(f"Built: {pages}. {errors} PDF error(s), "
                                         f"{len(self.findings)} item(s) in Missing and Images.")
        else:
            self.panels.setCurrentWidget(self.panels.checks)
            self.statusBar().showMessage("The paper did not compile. See PDF checks.")

    def fit(self) -> None:
        self.save_editor(quiet=True)
        self._run(lambda: self.project.fit(self.rules), self._fitted, "Fitting figures (several builds)…")

    def _ask_fit(self, readable, within):
        """Readable figures and the page limit conflict: the user decides."""
        def smallest(report):
            sizes = [c.text_after for c in report.changes if c.text_after]
            return f"{min(sizes):.1f} pt" if sizes else "not measured"
        box = QMessageBox(self)
        box.setWindowTitle("Readable figures or the page limit?")
        box.setText("Keeping every figure readable and staying within the page limit "
                    "cannot both be done. Choose one:")
        box.setInformativeText(
            f"Readable: {readable.pages_after} pages (limit {self.rules.page_limit}), "
            f"smallest figure text {smallest(readable)}.\n\n"
            f"Within the limit: {within.pages_after} pages, smallest figure text "
            f"{smallest(within)}.")
        keep = box.addButton("Keep figures readable", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Meet the page limit", QMessageBox.ButtonRole.AcceptRole)
        box.exec()
        return readable if box.clickedButton() is keep else within

    def _fitted(self, options: list) -> None:
        chosen = options[0] if len(options) == 1 else self.choose_fit(*options)
        self.project.apply_fit(chosen)
        self.panels.show_fit(describe(chosen))
        self.findings = self.project.findings(classify=self.classify_action.isChecked())
        self._refresh_views()
        self.rebuild_pending = True

    def fix_pdf(self) -> None:
        pdf = self.project.last_build.pdf
        fixed = pdf.with_name(pdf.stem + "-fixed.pdf")

        def job():
            embed_fonts(pdf, fixed)
            result = self.project.last_build
            result.pdf, result.issues = fixed, run_all_checks(fixed, self.rules)
            return result
        self._run(job, self._built, "Embedding fonts, then re-checking…")

    def toggle_classifier(self) -> None:
        on = self.classify_action.isChecked()
        self._run(lambda: self.project.findings(classify=on), self._classified,
                  "Running the AI-image classifier…" if on else "Updating…")

    def _classified(self, findings: list) -> None:
        self.findings = findings
        self._refresh_views()
        if self.editor and self.editor.block_id:
            self.show_block(self.editor.block_id)
        self.panels.setCurrentWidget(self.panels.images)
        self.statusBar().showMessage("Images checked.")

    def export(self) -> None:
        self.save_editor(quiet=True)
        default = str(self.project.source.with_name(self.project.source.stem + "-submission.zip"))
        path, _ = QFileDialog.getSaveFileName(self, "Export submission", default, "Zip (*.zip)")
        if path:
            self.export_to(Path(path))

    def export_to(self, path: Path) -> None:
        self._run(lambda: self.project.export(path, self.rules), self._exported, "Exporting…")

    def _exported(self, path: Path) -> None:
        self.statusBar().showMessage(f"Exported {path.name}")
        self._notice("Exported", f"Saved {path}\n\nPDF, LaTeX source, images, bibliography and a "
                                 f"report of every check.")

    def closeEvent(self, event) -> None:
        self.save_editor(quiet=True)
        for worker in list(self.workers):
            worker.wait(30000)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Prarup")
    app.setStyleSheet((Path(__file__).parent / "style.qss").read_text())
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        window.open_file(Path(sys.argv[1]))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

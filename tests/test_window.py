"""The desktop window, driven as a user drives it, on a real Word paper.

Headless (conftest sets QT_QPA_PLATFORM=offscreen). Each test waits for
the background work to finish, as a person would wait for the status bar.
"""

import shutil
import zipfile
from pathlib import Path

import pytest

from prarup.ui.editors import FigureEditor, FrontEditor, TextEditor
from prarup.ui.window import MainWindow

FIX = Path(__file__).parent / "fixtures"
PLOT = FIX / "latex_project" / "figs" / "accuracy.png"

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None or shutil.which("tectonic") is None,
    reason="pandoc and tectonic needed")


def idle(qtbot, window, timeout=180_000):
    qtbot.waitUntil(lambda: not window.busy and not window.rebuild_pending
                    and not window.workers and not window.rebuild_timer.isActive(), timeout=timeout)


@pytest.fixture
def window(qtbot, tmp_path):
    paper = tmp_path / "svm.docx"
    shutil.copy(FIX / "real" / "svm_diabetes.docx", paper)
    w = MainWindow()
    qtbot.addWidget(w)
    w.open_file(paper)
    idle(qtbot, w)
    return w


def figure(window, number):
    fig = window.project.m.figures()[number - 1]
    window.outline.select(fig.id)
    return fig


def missing_texts(window):
    return [window.panels.missing.item(i).text() for i in range(window.panels.missing.count())]


def test_opening_shows_outline_findings_and_the_pdf(window):
    tags = [window.outline.topLevelItem(i).text(0) for i in range(window.outline.topLevelItemCount())]
    assert tags[:4] == ["TITLE", "AUTH", "ABS", "KEY"]
    assert {"FIG 1", "FIG 2", "TAB 1", "H1", "P", "EQ", "REF"} <= set(tags)
    assert any("Fig. 1 has a caption but no image" in t for t in missing_texts(window))
    assert window.pdf.pageCount() >= 5
    assert isinstance(window.editor, FrontEditor)
    assert window.editor.title.text().startswith("Support vector machine")


def test_a_problem_in_the_list_jumps_to_its_block(window):
    row = next(i for i in range(window.panels.missing.count())
               if "FIG-03" in window.panels.missing.item(i).text())
    window.panels._clicked(window.panels.missing.item(row))
    assert isinstance(window.editor, FigureEditor)
    assert window.editor.block.number == 1


def test_adding_the_missing_image_clears_the_problem(qtbot, window):
    figure(window, 1)
    window.editor.set_image(PLOT, 0)
    idle(qtbot, window)
    assert not any("Fig. 1 has a caption but no image" in t for t in missing_texts(window))
    assert window.project.m.figures()[0].images[0].startswith("media/")


def test_editing_a_caption_is_saved_and_rebuilt(qtbot, window):
    fig = figure(window, 2)
    window.editor.caption.setPlainText("The SVM margin between two classes")
    window.save_editor()
    idle(qtbot, window)
    assert window.project.m.find(fig.id).caption == "The SVM margin between two classes"
    text = " ".join(window.project.last_build.pdf.read_bytes().decode("latin-1", "ignore").split())
    assert window.project.last_build.ok and text


def test_front_matter_edits_reach_the_title_block(qtbot, window):
    window.outline.select("front:keywords")
    window.editor.keywords.setText("SVM, diabetes, PIMA")
    window.save_editor()
    idle(qtbot, window)
    assert window.project.m.keywords == "SVM, diabetes, PIMA"


def test_retag_a_bold_paragraph_that_is_not_a_heading(qtbot, window):
    junk = next(b for b in window.project.m.blocks if b.kind == "heading" and "Suggested" in b.text)
    window.outline.select(junk.id)
    assert isinstance(window.editor, TextEditor)
    window.editor.kind.setCurrentIndex(0)                       # Paragraph
    window.save_editor()
    assert window.project.m.find(junk.id).kind == "para"


def test_fit_figures_makes_the_small_figure_readable(qtbot, window):
    assert any(i.code == "GEOM-03" for i in window.project.last_build.issues)
    window.choose_fit = lambda readable, within: readable
    window.fit()
    idle(qtbot, window, timeout=300_000)
    assert window.panels.fit.count() > 0
    assert not any(i.code == "GEOM-03" for i in window.project.last_build.issues)


def test_export_writes_the_bundle(qtbot, window, tmp_path):
    window.export_to(tmp_path / "out.zip")
    idle(qtbot, window)
    names = zipfile.ZipFile(tmp_path / "out.zip").namelist()
    assert "paper.pdf" in names and "prarup-report.md" in names
    assert "Exported" in window.statusBar().currentMessage()


def test_reopening_resumes_the_edits(qtbot, window):
    fig = figure(window, 3)
    window.editor.caption.setPlainText("Edited caption")
    window.save_editor()
    idle(qtbot, window)
    again = MainWindow()
    qtbot.addWidget(again)
    again.open_file(window.project.source)
    idle(qtbot, again)
    assert again.project.m.find(fig.id).caption == "Edited caption"

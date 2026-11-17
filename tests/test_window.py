"""The Tkinter window, driven the way a user drives it."""

import shutil
import time
import tkinter as tk
from pathlib import Path

import pytest
from PIL import Image

from prarup.checks import run_all_checks
from prarup.fix import find_ghostscript
from prarup.manuscript import Manuscript
from prarup.project import BuildResult, Project
from prarup.ui.window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"
PLOT = FIXTURES / "latex_project" / "figs" / "accuracy.png"
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="Pandoc required")


@pytest.fixture(scope="session")
def root():
    """One Tk root for every test: macOS Tk crashes if many are created and destroyed."""
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(str(error))
    yield root
    root.destroy()


@pytest.fixture
def window(root, monkeypatch):
    for child in root.winfo_children():
        child.destroy()
    monkeypatch.setattr("prarup.ui.window.messagebox.showerror",
                        lambda title, text, **kw: pytest.fail(f"{title}: {text}"))
    view = MainWindow(root)
    yield view
    while view.busy:
        root.update()
    if view.rebuild_timer:
        root.after_cancel(view.rebuild_timer)
    view.worker.shutdown()


def wait(window, builds=False):
    """Let the window finish its background jobs (and pending rebuilds, if asked)."""
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        window.root.update()
        if not window.busy and not (builds and (window.rebuild_timer or window.rebuild_waiting)):
            return
        time.sleep(0.02)
    pytest.fail("the window did not finish")


def open_copy(window, tmp_path, source):
    paper = tmp_path / source.name
    shutil.copyfile(source, paper)
    window.open_file(paper)
    wait(window)
    return window.project


@needs_pandoc
def test_outline_tags_every_block_and_marks_problems(window, tmp_path):
    m = open_copy(window, tmp_path, FIXTURES / "messy" / "svm_messy.docx").m
    rows = {key: window.outline.tree.item(key, "values") for key in window.outline.tree.get_children()}
    assert rows["abstract"][0] == "ABS" and rows["abstract"][1].startswith("⚠")
    no_caption = next(f for f in m.figures() if f.images and not f.caption)
    assert rows[no_caption.id][0].startswith("FIG") and "(no caption)" in rows[no_caption.id][1]
    assert "^" not in " ".join(str(v) for v in rows.values())       # markup is not shown


@needs_pandoc
def test_a_damaged_paper_is_fixed_through_the_window(window, tmp_path, monkeypatch):
    project = open_copy(window, tmp_path, FIXTURES / "messy" / "svm_messy.docx")
    codes = {f.code for f in window.findings}
    assert {"META-03", "META-04", "FIG-01", "FIG-03", "IMG-01", "IMG-02", "IMG-05"} <= codes

    # Clicking a problem in the Missing tab opens its block.
    rows = window.panels.missing.tree.get_children()
    caption_row = next(r for r in rows if window.panels.missing.tree.item(r, "values")[0] == "FIG-01")
    window.panels.missing.tree.selection_set(caption_row)
    window.root.update()
    assert window.key == window.panels.missing.blocks[caption_row]

    window.editor.caption.insert("1.0", "The SVM technique.")
    window.save_editor()
    window.jump("abstract")
    window.editor.abstract.insert("1.0", "We classify diabetes with a support vector machine.")
    window.editor.keywords.insert(0, "SVM, diabetes")
    window.save_editor()

    ai = next(f for f in project.m.figures() if "Overview" in f.caption)
    window.jump(ai.id)
    assert "declared AI-generated" in window.panels.images.tree.item(
        window.panels.images.tree.get_children()[0], "values")[4]
    window.set_image(PLOT, 0)
    missing = next(f for f in project.m.figures() if not f.images)
    window.jump(missing.id)
    other = tmp_path / "pipeline.png"
    Image.effect_noise((1200, 800), 60).convert("RGB").save(other)     # a different picture
    window.set_image(other, 0)
    duplicate = next(f for f in project.m.figures() if "again" in f.caption)
    window.jump(duplicate.id)
    monkeypatch.setattr("prarup.ui.window.messagebox.askyesno", lambda *a, **kw: True)
    window.delete_block()

    left = {f.code for f in window.findings}
    assert not {"META-03", "META-04", "FIG-01", "FIG-03", "IMG-02", "IMG-05"} & left
    if shutil.which("tectonic"):
        wait(window, builds=True)
        assert window.preview.pdf and window.project.last_build.ok
        window.export_to(tmp_path / "out.zip")
        wait(window)
        assert (tmp_path / "out.zip").is_file()


@needs_pandoc
def test_retagging_a_paragraph_as_a_heading(window, tmp_path):
    project = open_copy(window, tmp_path, FIXTURES / "sample.docx")
    para = next(b for b in project.m.blocks if b.kind == "para")
    window.jump(para.id)
    window.editor.kind.set("heading")
    window.save_editor()
    assert project.m.find(para.id).kind == "heading"
    assert window.outline.tree.item(para.id, "values")[0] == "H1"


@needs_pandoc
def test_editing_a_table_cell(window, tmp_path):
    project = open_copy(window, tmp_path, FIXTURES / "real" / "svm_diabetes.docx")
    table = project.m.tables()[0]
    window.jump(table.id)
    cell, field = window.editor.cells[1]
    field.delete(0, "end")
    field.insert(0, "Edited cell")
    window.save_editor()
    assert "Edited cell" in (project.folder / "manuscript.json").read_text()


@needs_pandoc
@pytest.mark.skipif(shutil.which("tectonic") is None, reason="Tectonic required")
def test_fit_figures_lets_the_user_choose(window, tmp_path):
    open_copy(window, tmp_path, FIXTURES / "messy" / "svm_messy.docx")
    wait(window, builds=True)
    chosen = []
    window.choose_fit = lambda readable, within: chosen.append(readable) or readable
    window.fit()
    wait(window, builds=True)
    assert "pt" in window.panels.fit.get("1.0", "end")
    assert window.project.last_build.ok


def test_pdf_navigation(window):
    window.preview.load(FIXTURES / "six_pages.pdf")
    window.root.update()
    window.preview.next.invoke()
    assert window.preview.page_label.cget("text") == "Page 2 / 6"


@pytest.mark.parametrize("filename", ["six_pages.pdf", "unembedded.pdf"])
def test_fix_pdf_explains_result(window, tmp_path, monkeypatch, filename):
    if filename == "unembedded.pdf" and not find_ghostscript():
        pytest.skip("Ghostscript required")
    source = tmp_path / "sample.docx"
    project = Project(source, tmp_path, Manuscript(str(source)))
    (tmp_path / "build").mkdir()
    pdf = tmp_path / "build" / "paper.pdf"
    shutil.copyfile(FIXTURES / filename, pdf)
    project.last_build = BuildResult(pdf, run_all_checks(pdf, window.rules))
    window.project = project
    window.preview.load(pdf)
    notices = []
    monkeypatch.setattr("prarup.ui.window.messagebox.showinfo",
                        lambda _, text, **kw: notices.append(text))
    window.fix()
    wait(window)
    fixed = tmp_path / "build" / "paper-fixed.pdf"
    if filename == "six_pages.pdf":
        assert notices and "Nothing" in notices[0] and not fixed.exists()
    else:
        assert fixed.is_file() and window.preview.pdf == fixed
        assert not any(issue.can_fix for issue in project.last_build.issues)

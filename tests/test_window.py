import shutil
import time
import tkinter as tk
from pathlib import Path

import pytest

from prarup.checks import run_all_checks
from prarup.fix import find_ghostscript
from prarup.manuscript import Manuscript
from prarup.project import BuildResult, Project
from prarup.ui.window import MainWindow

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def window():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(str(error))
    view = MainWindow(root)
    yield view
    view.worker.shutdown()
    root.destroy()


def wait_for_window(window):
    deadline = time.monotonic() + 30
    while window.busy and time.monotonic() < deadline:
        window.root.update()
        time.sleep(0.02)
    assert not window.busy


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="Pandoc required")
def test_open_and_edit_caption(window, tmp_path):
    paper = tmp_path / "sample.docx"
    shutil.copyfile(FIXTURES / paper.name, paper)
    window.open_file(paper)
    wait_for_window(window)
    assert window.project.source == paper
    figure = window.project.m.figures()[0]
    window.outline.selection_set(window.keys.index(figure.id))
    window.edit()
    dialog = next(w for w in window.root.winfo_children() if isinstance(w, tk.Toplevel))
    frame = next(w for w in dialog.winfo_children() if isinstance(w, tk.Frame))
    text = next(w for w in frame.winfo_children() if isinstance(w, tk.Text))
    text.delete("1.0", "end")
    text.insert("1.0", "Revised caption")
    next(w for w in dialog.winfo_children() if isinstance(w, tk.Button)).invoke()
    wait_for_window(window)
    assert window.project.m.find(figure.id).caption == "Revised caption"
    assert "Revised caption" in (window.project.folder / "manuscript.json").read_text()


def test_pdf_navigation(window):
    window.preview.load(FIXTURES / "six_pages.pdf")
    window.root.update()
    window.preview.next.invoke()
    assert window.preview.page_label.cget("text") == "Page 2 / 6"
    assert window.preview.preview_area.find_all()


@pytest.mark.parametrize("filename", ["six_pages.pdf", "unembedded.pdf"])
def test_fix_pdf_explains_result(window, tmp_path, monkeypatch, filename):
    if filename == "unembedded.pdf" and not find_ghostscript():
        pytest.skip("Ghostscript required")
    source = tmp_path / "sample.docx"
    project = Project(source, tmp_path, Manuscript(str(source)))
    build = tmp_path / "build"
    build.mkdir()
    pdf = build / "paper.pdf"
    shutil.copyfile(FIXTURES / filename, pdf)
    project.last_build = BuildResult(pdf, run_all_checks(pdf, window.rules))
    monkeypatch.setattr(window, "project", project)
    window.preview.load(pdf)
    notices = []
    monkeypatch.setattr("prarup.ui.window.messagebox.showinfo", lambda _, text, **kw: notices.append(text))

    window.fix()
    wait_for_window(window)

    fixed = build / "paper-fixed.pdf"
    if filename == "six_pages.pdf":
        assert notices and "no issues" in notices[0]
        assert not fixed.exists()
    else:
        assert fixed.is_file() and window.preview.pdf == fixed
        assert not any(issue.can_fix for issue in project.last_build.issues)
        assert "Saved paper-fixed.pdf" in window.status.get()

"""Tests for the window.

Run headless. The widgets are created and driven, but nothing is drawn,
so these work in CI and over ssh.
"""

import shutil
from pathlib import Path

import pytest

from prarup.gui import MainWindow, build_paper, format_issue
from prarup.models import Issue, Rules

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------- pure bits

def test_error_line_is_labelled():
    line = format_issue(Issue("FONT-02", "X is Type3", "error"))
    assert line.startswith("ERROR")
    assert "FONT-02" in line


def test_fixable_issue_says_so():
    assert "[can fix]" in format_issue(Issue("F", "m", "error", can_fix=True))


def test_unfixable_issue_does_not():
    assert "[can fix]" not in format_issue(Issue("F", "m", "error"))


# ---------------------------------------------------------------- the window

def test_window_starts_with_build_disabled(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window.build_button.isEnabled()
    assert not window.fix_button.isEnabled()


def test_loading_a_file_enables_build(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.load(FIXTURES / "six_pages.pdf")
    assert window.build_button.isEnabled()
    assert "six_pages.pdf" in window.status.text()


def test_issues_appear_in_the_list(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show_issues([
        Issue("FONT-02", "X is Type3", "error"),
        Issue("GEOM-01", "2 pages over", "warning"),
    ])
    assert window.issue_list.count() == 2
    assert "FONT-02" in window.issue_list.item(0).text()
    assert "1 error(s), 1 warning(s)" in window.status.text()


def test_clean_result_says_so(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show_issues([])
    assert window.issue_list.count() == 0
    assert "All checks passed" in window.status.text()


def test_fix_button_follows_what_is_fixable(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.show_issues([Issue("FONT-02", "Type3", "error", can_fix=False)])
    assert not window.fix_button.isEnabled()

    window.show_issues([Issue("FONT-01", "not embedded", "error", can_fix=True)])
    assert window.fix_button.isEnabled()


def test_a_failed_build_is_shown_not_swallowed(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.on_failed("Undefined control sequence")
    assert "failed" in window.status.text().lower()
    assert "Undefined control sequence" in window.issue_list.item(0).text()


# ------------------------------------------------------- the shared pipeline

def test_build_paper_on_a_pdf_just_checks_it(tmp_path):
    """A .pdf needs no compilation, so the pipeline should skip straight
    to the checks rather than trying to build it."""
    pdf, issues = build_paper(
        FIXTURES / "mpl_type3.pdf", tmp_path, "ieee", Rules()
    )
    assert pdf == FIXTURES / "mpl_type3.pdf"
    assert "FONT-02" in [i.code for i in issues]


@pytest.mark.skipif(
    shutil.which("tectonic") is None or shutil.which("pandoc") is None,
    reason="tectonic and pandoc needed",
)
def test_build_paper_takes_docx_all_the_way(tmp_path):
    """The window and the CLI must run the same pipeline."""
    pdf, issues = build_paper(
        FIXTURES / "sample.docx", tmp_path, "ieee", Rules()
    )
    assert pdf.exists()
    assert issues == []

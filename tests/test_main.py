"""Tests for the command line behaviour."""

import shutil
from pathlib import Path

import pytest

from prarup.main import main

FIXTURES = Path(__file__).parent / "fixtures"


def run(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["prarup", *argv])
    return main()


def test_clean_file_exits_zero(monkeypatch, capsys):
    code = run(monkeypatch, "check", str(FIXTURES / "six_pages.pdf"))
    assert code == 0
    assert "all checks passed" in capsys.readouterr().out


def test_blocking_error_exits_one(monkeypatch):
    """Non-zero on error, so this can gate a submission script."""
    assert run(monkeypatch, "check", str(FIXTURES / "mpl_type3.pdf")) == 1


def test_warning_alone_still_exits_zero(monkeypatch):
    """Over the page limit is worth saying, but it does not block."""
    code = run(monkeypatch, "check", str(FIXTURES / "eight_pages.pdf"),
               "--page-limit", "6")
    assert code == 0


def test_missing_file_exits_two(monkeypatch, capsys):
    code = run(monkeypatch, "check", "nope.pdf")
    assert code == 2
    assert "does not exist" in capsys.readouterr().err


def test_report_names_the_problem(monkeypatch, capsys):
    run(monkeypatch, "check", str(FIXTURES / "mpl_type3.pdf"))
    out = capsys.readouterr().out
    assert "FONT-02" in out
    assert "Type3" in out


def test_preset_supplies_the_page_limit(monkeypatch, capsys):
    """The shipped ieee preset sets 6 pages, so an 8 page file warns."""
    run(monkeypatch, "check", str(FIXTURES / "eight_pages.pdf"))
    assert "GEOM-01" in capsys.readouterr().out


def test_explicit_page_limit_overrides_the_preset(monkeypatch, capsys):
    run(monkeypatch, "check", str(FIXTURES / "eight_pages.pdf"),
        "--page-limit", "10")
    assert "all checks passed" in capsys.readouterr().out


def test_bad_rules_file_exits_two(monkeypatch, capsys, tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("page_limmit: 4\n")
    code = run(monkeypatch, "check", str(FIXTURES / "six_pages.pdf"),
               "--rules", str(bad))
    assert code == 2
    assert "page_limmit" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript not installed")
def test_fix_flag_repairs_and_rechecks(monkeypatch, capsys, tmp_path):
    """--fix must verify its own work, not assume it."""
    target = tmp_path / "unembedded.pdf"
    shutil.copy(FIXTURES / "unembedded.pdf", target)

    code = run(monkeypatch, "check", str(target), "--fix")
    out = capsys.readouterr().out

    assert "repaired ->" in out
    assert "all checks passed" in out
    assert code == 0


@pytest.mark.skipif(shutil.which("gs") is None, reason="ghostscript not installed")
def test_fix_does_not_claim_success_on_type3(monkeypatch, capsys, tmp_path):
    """Type3 is unfixable, so --fix must still report it and exit 1."""
    target = tmp_path / "type3.pdf"
    shutil.copy(FIXTURES / "mpl_type3.pdf", target)

    code = run(monkeypatch, "check", str(target), "--fix")

    assert "FONT-02" in capsys.readouterr().out
    assert code == 1


def test_a_corrupt_pdf_exits_two_without_a_traceback(monkeypatch, capsys, tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_text("garbage")
    assert run(monkeypatch, "check", str(bad)) == 2
    assert "not a readable PDF" in capsys.readouterr().err


def test_build_refuses_an_unsupported_file_type(monkeypatch, capsys, tmp_path):
    """A .txt would otherwise reach pandoc or Tectonic and fail obscurely."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")
    assert run(monkeypatch, "build", str(notes)) == 2
    assert ".docx, .tex or .zip" in capsys.readouterr().err


def test_build_reports_a_missing_source(monkeypatch, capsys, tmp_path):
    assert run(monkeypatch, "build", str(tmp_path / "gone.tex")) == 2
    assert "does not exist" in capsys.readouterr().err


needs_tools = pytest.mark.skipif(
    shutil.which("tectonic") is None or shutil.which("pandoc") is None,
    reason="tectonic and pandoc needed")
REAL = FIXTURES / "real"


@needs_tools
def test_inspect_lists_what_a_real_paper_is_missing(monkeypatch, capsys, tmp_path):
    paper = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", paper)
    code = run(monkeypatch, "inspect", str(paper))
    out = capsys.readouterr().out
    assert code == 1                                   # Fig. 1 has no image: an error
    assert "FIG-03  Fig. 1 has a caption but no image." in out
    assert "dpi" in out


@needs_tools
def test_build_a_real_word_paper(monkeypatch, capsys, tmp_path):
    paper = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", paper)
    run(monkeypatch, "build", str(paper))
    out = capsys.readouterr().out
    assert "built ->" in out
    assert (tmp_path / "svm-prarup" / "build" / "paper.pdf").exists()
    assert "GEOM-03" in out                            # Fig. 3 prints at 3.9 pt


@needs_tools
def test_fit_then_the_figure_is_readable(monkeypatch, capsys, tmp_path):
    paper = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", paper)
    run(monkeypatch, "fit", str(paper))
    out = capsys.readouterr().out
    assert "Fig. 3" in out and "text 7.0 pt" in out
    assert "GEOM-03" not in out.split("built ->")[1]


@needs_tools
def test_typed_metadata_with_latex_special_characters(monkeypatch, capsys, tmp_path):
    """Typed "12%" once started a LaTeX comment and cut the abstract short."""
    import pymupdf
    paper = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", paper)
    run(monkeypatch, "build", str(paper), "--title", "R&D at 100% of R_2",
        "--abstract", "We show a 12% gain & R_2 improves.")
    text = " ".join(pymupdf.open(tmp_path / "svm-prarup" / "build" / "paper.pdf")[0].get_text().split())
    assert "R&D at 100% of R_2" in text
    assert "We show a 12% gain & R_2 improves." in text


@needs_tools
def test_export_writes_a_zip(monkeypatch, capsys, tmp_path):
    paper = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", paper)
    assert run(monkeypatch, "export", str(paper), "-o", str(tmp_path / "out.zip")) == 0
    assert (tmp_path / "out.zip").exists()


def test_fit_refuses_a_pdf(monkeypatch, capsys):
    assert run(monkeypatch, "fit", str(FIXTURES / "six_pages.pdf")) == 2
    assert "needs the .docx, .tex or .zip" in capsys.readouterr().err

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
    """A .txt would otherwise reach Tectonic and fail with a TeX error."""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello")
    assert run(monkeypatch, "build", str(notes), "--outdir", str(tmp_path)) == 2
    assert ".docx, .tex or .pdf" in capsys.readouterr().err


def test_build_reports_a_missing_source(monkeypatch, capsys, tmp_path):
    code = run(monkeypatch, "build", str(tmp_path / "gone.tex"),
               "--outdir", str(tmp_path))
    assert code == 2
    assert "does not exist" in capsys.readouterr().err

"""Tests for the command line behaviour."""

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

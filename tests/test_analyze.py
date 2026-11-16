import shutil
from pathlib import Path

import pytest

from prarup.analyze import _roman, analyze
from prarup.ingest import open_paper

FIX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")


def findings(source, tmp_path):
    m = open_paper(source, tmp_path)
    return [(f.code, f.message) for f in analyze(m, tmp_path)]


def test_yolo_uncaptioned_figures_and_tables(tmp_path):
    codes = [c for c, _ in findings(FIX / "real" / "yolo_football.docx", tmp_path)]
    assert codes.count("FIG-01") == 3 and codes.count("TAB-01") == 2
    assert "STR-01" not in codes


def test_svm_real_gaps_only(tmp_path):
    found = findings(FIX / "real" / "svm_diabetes.docx", tmp_path)
    assert ("FIG-03", "Fig. 1 has a caption but no image.") in found
    assert ("FIG-02", "Fig. 2 is never mentioned in the text.") in found
    assert not any(c == "TAB-02" and "Table 1 " in msg for c, msg in found)
    assert not any(c == "STR-02" for c, _ in found)


def test_latex_missing_image_ghost_citation_unused_reference(tmp_path):
    codes = dict(findings(FIX / "latex_project" / "main.tex", tmp_path))
    assert "FIG-03" in codes
    assert codes["REF-02"] == "Citation [ghost] has no matching reference."
    assert codes["REF-03"] == "Reference [unused] is never cited."


def test_roman_numerals():
    assert [_roman(r) for r in ["I", "IV", "VI", "IX", "XII"]] == [1, 4, 6, 9, 12]

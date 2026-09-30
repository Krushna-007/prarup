"""Tests for automatic repair.

The rule these enforce: a repair is only reported as successful if
re-running the check on the output confirms it. Ghostscript exits zero on
a file it did not change, so an exit code proves nothing.
"""

import shutil
from pathlib import Path

import pytest

from prarup.checks import check_fonts
from prarup.fix import GhostscriptNotFound, embed_fonts

FIXTURES = Path(__file__).parent / "fixtures"

needs_gs = pytest.mark.skipif(
    shutil.which("gs") is None, reason="ghostscript not installed"
)


@needs_gs
def test_embedding_removes_the_font_issue(tmp_path):
    """The repair must actually repair, verified by re-checking."""
    source = FIXTURES / "unembedded.pdf"
    assert check_fonts(source) != []          # broken to begin with

    repaired = embed_fonts(source, tmp_path / "fixed.pdf")

    assert repaired.exists()
    assert check_fonts(repaired) == []        # and clean afterwards


@needs_gs
def test_ghostscript_cannot_repair_type3(tmp_path):
    """Documented Ghostscript limitation, asserted rather than assumed.

    If this ever starts passing, the auto-fix branch in checks.py can be
    simplified. Until then FONT-02 must stay marked unfixable.
    """
    repaired = embed_fonts(FIXTURES / "mpl_type3.pdf", tmp_path / "out.pdf")
    codes = [i.code for i in check_fonts(repaired)]
    assert "FONT-02" in codes, "Ghostscript unexpectedly fixed a Type3 font"

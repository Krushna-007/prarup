from pathlib import Path

from prarup.checks import check_fonts

FIXTURES = Path(__file__).parent / "fixtures"


def test_type3_font_is_reported():
    """matplotlib's default export uses Type3, which IEEE rejects."""
    issues = check_fonts(FIXTURES / "mpl_type3.pdf")
    assert [i.code for i in issues] == ["FONT-02"]


def test_type3_cannot_be_fixed_automatically():
    """Ghostscript cannot repair Type3. The figure has to be remade."""
    issue = check_fonts(FIXTURES / "mpl_type3.pdf")[0]
    assert issue.can_fix is False


def test_type3_is_not_also_reported_as_unembedded():
    """A Type3 font reports ext='n/a' but is not a missing-font problem.

    Reporting both FONT-01 and FONT-02 for one font would send the user
    to Ghostscript, which cannot help.
    """
    codes = [i.code for i in check_fonts(FIXTURES / "mpl_type3.pdf")]
    assert "FONT-01" not in codes


def test_corrected_figure_is_clean():
    """pdf.fonttype = 42 is the fix, so the output must come back empty."""
    assert check_fonts(FIXTURES / "mpl_truetype.pdf") == []

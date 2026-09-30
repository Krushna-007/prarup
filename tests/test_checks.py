from pathlib import Path

from prarup.checks import check_fonts, check_page_count, check_security
from prarup.models import Rules

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


def test_paper_within_the_limit_is_clean():
    assert check_page_count(FIXTURES / "six_pages.pdf", Rules(page_limit=6)) == []


def test_paper_over_the_limit_is_reported():
    issues = check_page_count(FIXTURES / "eight_pages.pdf", Rules(page_limit=6))
    assert len(issues) == 1
    assert issues[0].code == "GEOM-01"
    assert "2 page" in issues[0].message


def test_page_limit_is_a_warning_not_an_error():
    """Being over the limit is for the author to fix, not us."""
    issues = check_page_count(FIXTURES / "eight_pages.pdf", Rules(page_limit=6))
    assert issues[0].severity == "warning"
    assert issues[0].can_fix is False


def test_plain_pdf_has_no_security_problem():
    assert check_security(FIXTURES / "six_pages.pdf") == []


def test_encrypted_pdf_is_reported():
    issues = check_security(FIXTURES / "protected.pdf")
    assert len(issues) == 1
    assert issues[0].code == "DOC-01"


def test_encryption_can_be_removed_automatically():
    """Stripping encryption is a safe, deterministic repair."""
    assert check_security(FIXTURES / "protected.pdf")[0].can_fix is True

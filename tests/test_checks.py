from pathlib import Path

from prarup.checks import check_fonts, check_page_count, check_security, run_all_checks
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


def test_run_all_checks_collects_from_every_check():
    issues = run_all_checks(FIXTURES / "mpl_type3.pdf", Rules())
    assert "FONT-02" in [i.code for i in issues]


def test_run_all_checks_returns_nothing_for_a_clean_file():
    assert run_all_checks(FIXTURES / "six_pages.pdf", Rules(page_limit=6)) == []


def test_errors_are_listed_before_warnings():
    """The report is read top down, so the blocking items come first."""
    issues = run_all_checks(FIXTURES / "eight_pages.pdf", Rules(page_limit=1))
    severities = [i.severity for i in issues]
    assert severities == sorted(severities, key=lambda s: s != "error")


def test_unembedded_font_is_reported():
    issues = check_fonts(FIXTURES / "unembedded.pdf")
    assert [i.code for i in issues] == ["FONT-01"]
    assert "Helvetica" in issues[0].message


def test_unembedded_font_can_be_fixed():
    """Unlike Type3, Ghostscript can embed a referenced font in place."""
    assert check_fonts(FIXTURES / "unembedded.pdf")[0].can_fix is True


def _same_font_on_pages(path, pages, fontname="helv"):
    """A PDF that uses one unembedded font on several pages."""
    import pymupdf

    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_text((72, 100), "text", fontname=fontname)
    doc.save(path)
    doc.close()
    return path


def test_one_font_on_many_pages_is_reported_once(tmp_path):
    """A real paper repeats a font on every page. One line per font, not per page."""
    pdf = _same_font_on_pages(tmp_path / "many.pdf", 5)
    issues = check_fonts(pdf)
    assert len(issues) == 1
    assert "pages 1-5" in issues[0].message


def test_single_page_is_named(tmp_path):
    pdf = _same_font_on_pages(tmp_path / "one.pdf", 1)
    assert "page 1" in check_fonts(pdf)[0].message


def test_page_list_collapses_runs():
    from prarup.checks import describe_pages
    assert describe_pages([1]) == "page 1"
    assert describe_pages([3, 1, 2]) == "pages 1-3"
    assert describe_pages([2, 5, 7, 8, 9]) == "pages 2, 5, 7-9"


def test_subset_prefix_is_dropped_from_the_name():
    """ABCDEF+Times is the same font as GHIJKL+Times. Name it once, plainly."""
    from prarup.checks import plain_font_name
    assert plain_font_name("FHXFSG+TimesNewRomanPSMT") == "TimesNewRomanPSMT"
    assert plain_font_name("Helvetica") == "Helvetica"


def test_a_font_with_no_name_is_still_described():
    """Ghostscript rewrites Type3 fonts with an empty name."""
    from prarup.checks import plain_font_name
    assert plain_font_name("") == "an unnamed font"


def test_type3_message_says_how_to_fix_it():
    """The author cannot act on "Type3" alone. Tell them the setting."""
    message = check_fonts(FIXTURES / "mpl_type3.pdf")[0].message
    assert "pdf.fonttype" in message


def test_a_file_that_is_not_a_pdf_raises_a_clear_error(tmp_path):
    import pytest
    from prarup.checks import UnreadablePdf

    bad = tmp_path / "paper.pdf"
    bad.write_text("not a pdf")
    with pytest.raises(UnreadablePdf, match="paper.pdf is not a readable PDF"):
        run_all_checks(bad, Rules())


def test_a_tex_file_is_not_mistaken_for_a_pdf(tmp_path):
    import pytest
    from prarup.checks import UnreadablePdf

    tex = tmp_path / "paper.tex"
    tex.write_text(r"\documentclass{article}")
    with pytest.raises(UnreadablePdf):
        run_all_checks(tex, Rules())


def _with_bookmarks(path):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    doc.set_toc([[1, "Introduction", 1], [1, "Results", 2]])
    doc.save(path)
    doc.close()
    return path


def test_bookmarks_are_reported(tmp_path):
    """hyperref adds bookmarks, which some IEEE pipelines reject."""
    from prarup.checks import check_bookmarks

    issues = check_bookmarks(_with_bookmarks(tmp_path / "marked.pdf"))
    assert [i.code for i in issues] == ["DOC-02"]
    assert "2 bookmarks" in issues[0].message
    assert issues[0].severity == "warning"


def test_no_bookmarks_is_clean():
    from prarup.checks import check_bookmarks

    assert check_bookmarks(FIXTURES / "six_pages.pdf") == []


def test_run_all_checks_includes_bookmarks(tmp_path):
    issues = run_all_checks(_with_bookmarks(tmp_path / "marked.pdf"), Rules())
    assert "DOC-02" in [i.code for i in issues]

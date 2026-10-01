"""Turning a LaTeX fragment into a Document."""

from prarup.document import document_from_latex


def test_first_section_becomes_the_title():
    doc = document_from_latex(r"\section{A Study of Things}" "\n\nText.")
    assert doc.title == "A Study of Things"


def test_the_title_is_removed_from_the_body():
    doc = document_from_latex(r"\section{A Study of Things}" "\n\nText.")
    assert "A Study of Things" not in doc.body


def test_pandoc_labels_are_tolerated():
    """pandoc writes \\section{X}\\label{x}, not a bare \\section."""
    doc = document_from_latex(r"\section{Sample Paper}\label{sample-paper}" "\n\nText.")
    assert doc.title == "Sample Paper"


def test_remaining_headings_are_promoted_one_level():
    """Consuming the top heading as the title leaves everything else a
    level too deep, so Introduction would render as a subsection."""
    source = (
        r"\section{Paper}\label{p}" "\n\n"
        r"\subsection{Introduction}\label{i}" "\n\nText.\n\n"
        r"\subsubsection{Detail}\label{d}" "\n\nMore.\n"
    )
    doc = document_from_latex(source)
    assert r"\section{Introduction}" in doc.body
    assert r"\subsection{Detail}" in doc.body
    assert r"\subsection{Introduction}" not in doc.body


def test_a_lone_section_with_no_subsections_is_kept():
    """One \\section and nothing nested is a real section, not a title
    wrapper, so it stays even when a title is supplied."""
    source = r"\section{Introduction}" "\n\nText."
    doc = document_from_latex(source, title="My Real Title")
    assert doc.title == "My Real Title"
    assert r"\section{Introduction}" in doc.body


def test_a_fragment_with_no_headings_keeps_its_body():
    doc = document_from_latex("Just some text.")
    assert doc.title == ""
    assert doc.body.strip() == "Just some text."


def test_figures_get_a_placement_specifier():
    """pandoc writes a bare \\begin{figure}, which LaTeX is free to float to
    the very top of the column. In IEEEtran that lands it above the
    abstract, which is wrong on the page."""
    doc = document_from_latex("\\begin{figure}\n\\centering\nX\n\\end{figure}")
    assert r"\begin{figure}[htbp]" in doc.body


def test_existing_placement_is_left_alone():
    """If the author already chose a placement, respect it."""
    doc = document_from_latex("\\begin{figure}[t]\n\\centering\nX\n\\end{figure}")
    assert r"\begin{figure}[t]" in doc.body
    assert r"\begin{figure}[htbp]" not in doc.body


def test_starred_figures_are_left_alone():
    """figure* spans both columns and its placement rules differ."""
    doc = document_from_latex("\\begin{figure*}\nX\n\\end{figure*}")
    assert r"\begin{figure*}" in doc.body
    assert "htbp" not in doc.body


def test_a_lone_top_heading_is_consumed_even_with_an_explicit_title():
    """A .docx whose only top-level heading is the paper name must not
    render that heading as section I, whatever title the user typed."""
    source = (
        r"\section{Sample Paper}\label{s}" "\n\n"
        r"\subsection{Introduction}\label{i}" "\n\nText.\n"
    )
    doc = document_from_latex(source, title="A Better Title")
    assert doc.title == "A Better Title"
    assert "Sample Paper" not in doc.body
    assert r"\section{Introduction}" in doc.body


def test_several_top_level_sections_are_left_alone():
    """Here the sections are real content, not a document title."""
    source = (
        r"\section{Introduction}" "\n\nText.\n\n"
        r"\section{Results}" "\n\nMore.\n"
    )
    doc = document_from_latex(source, title="My Paper")
    assert r"\section{Introduction}" in doc.body
    assert r"\section{Results}" in doc.body


def test_several_top_level_sections_with_no_title_keeps_them_all():
    """Nothing to promote, and the first section is not a title."""
    source = r"\section{Introduction}" "\n\nA.\n\n" r"\section{Results}" "\n\nB.\n"
    doc = document_from_latex(source)
    assert doc.title == ""
    assert r"\section{Introduction}" in doc.body
    assert r"\section{Results}" in doc.body

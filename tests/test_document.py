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


def test_an_explicit_title_wins_and_nothing_is_promoted():
    source = r"\section{Introduction}" "\n\nText."
    doc = document_from_latex(source, title="My Real Title")
    assert doc.title == "My Real Title"
    assert r"\section{Introduction}" in doc.body


def test_a_fragment_with_no_headings_keeps_its_body():
    doc = document_from_latex("Just some text.")
    assert doc.title == ""
    assert doc.body.strip() == "Just some text."

"""Finding the title, authors and abstract in a Word paper.

The fragments are pandoc's real LaTeX output for each layout, copied from
running pandoc on .docx files built that way.
"""

from prarup.document import document_from_latex
from prarup.frontmatter import escape_latex, latex_to_plain, split_front_matter
from prarup.models import Author

# Plain paragraphs, laid out like IEEE's own Word template
IEEE_STYLE = r"""\textbf{Federated Learning on Drones}

Asha Rao, DA-IICT

Vikram Shah, IIT Bombay

\textbf{\emph{Abstract}---We study federated learning on UAV swarms and
show a 12\% gain.}

\emph{Keywords}---federated learning, UAV

\section{Introduction}\label{introduction}

Intro text.
"""

# One paragraph per author, lines broken with Shift+Enter
MULTI_LINE = r"""FEDERATED LEARNING ON DRONES

Asha Rao\textsuperscript{1}\\
Dept. of ICT, DA-IICT\\
Gandhinagar, India\\
asha@daiict.ac.in

Vikram Shah\textsuperscript{2}\\
IIT Bombay\\
Mumbai, India

ABSTRACT: We study federated learning on UAV swarms.

Index Terms---federated learning, UAV

\section{Introduction}\label{introduction}

Intro.
"""

# What pandoc leaves in the body when Word's Abstract style was used
STYLED_ABSTRACT = r"""Abstract

We study federated learning on UAV swarms.

\section{Introduction}\label{introduction}

Intro.
"""


def test_ieee_layout_gives_title_authors_abstract_and_keywords():
    found, body = split_front_matter(IEEE_STYLE)
    assert found["title"] == "Federated Learning on Drones"
    assert found["authors"] == [Author("Asha Rao", "DA-IICT"), Author("Vikram Shah", "IIT Bombay")]
    assert found["abstract"] == "We study federated learning on UAV swarms and show a 12% gain."
    assert found["keywords"] == "federated learning, UAV"


def test_front_matter_is_removed_from_the_body():
    """Left in, it would print a second time as ordinary text."""
    _, body = split_front_matter(IEEE_STYLE)
    assert body.lstrip().startswith(r"\section{Introduction}")
    assert "Asha Rao" not in body


def test_multi_line_author_blocks():
    found, _ = split_front_matter(MULTI_LINE)
    assert found["title"] == "FEDERATED LEARNING ON DRONES"
    assert found["authors"] == [
        Author("Asha Rao", "Dept. of ICT, DA-IICT, Gandhinagar, India, asha@daiict.ac.in"),
        Author("Vikram Shah", "IIT Bombay, Mumbai, India"),
    ]
    assert found["abstract"] == "We study federated learning on UAV swarms."
    assert found["keywords"] == "federated learning, UAV"


def test_abstract_heading_on_its_own_line():
    found, body = split_front_matter(STYLED_ABSTRACT)
    assert found["abstract"] == "We study federated learning on UAV swarms."
    assert body.lstrip().startswith(r"\section{Introduction}")


def test_several_authors_on_one_line():
    found, _ = split_front_matter(
        "Paper Title\n\nAsha Rao, Vikram Shah and Om Patel\n\nAbstract---Text.\n\n\\section{A}\n"
    )
    assert [a.name for a in found["authors"]] == ["Asha Rao", "Vikram Shah", "Om Patel"]


def test_without_an_abstract_nothing_is_taken_from_the_body():
    """No abstract, no safe way to tell front matter from the first paragraph."""
    fragment = "Some opening paragraph.\n\nAnother one.\n\n\\section{Introduction}\n\nText.\n"
    found, body = split_front_matter(fragment)
    assert found == {}
    assert body == fragment


def test_nothing_before_the_first_section_is_fine():
    fragment = "\\section{Introduction}\n\nText.\n"
    assert split_front_matter(fragment) == ({}, fragment)


def test_latex_to_plain():
    assert latex_to_plain(r"\textbf{\emph{Abstract}---A 12\% gain \& more}") == "Abstract—A 12% gain & more"
    assert latex_to_plain(r"Rao\textsuperscript{1}") == "Rao"


def test_escape_latex_protects_every_special_character():
    assert escape_latex("12% & $5 #1 R_2 {x}") == r"12\% \& \$5 \#1 R\_2 \{x\}"


def test_escape_latex_keeps_backslash_and_tilde_printable():
    assert escape_latex(r"a\b ~c ^d") == r"a\textbackslash{}b \textasciitilde{}c \textasciicircum{}d"


def test_typed_fields_are_escaped_into_the_document():
    """Typed "12%" used to start a LaTeX comment and silently cut the abstract."""
    doc = document_from_latex(
        "\\section{A}\n\\section{B}\n",
        title="R&D at 100%",
        authors=[Author("Asha_Rao", "Dept. #4")],
        abstract="We show a 12% gain & R_2 improves.",
    )
    assert doc.title == r"R\&D at 100\%"
    assert doc.authors == [Author(r"Asha\_Rao", r"Dept. \#4")]
    assert doc.abstract == r"We show a 12\% gain \& R\_2 improves."


def test_a_title_taken_from_the_first_heading_is_not_escaped_twice():
    doc = document_from_latex("\\section{R\\&D Paper}\n\\subsection{Intro}\n")
    assert doc.title == r"R\&D Paper"


def test_latex_to_plain_reads_pandocs_escapes_for_caret_and_tilde():
    assert latex_to_plain(r"(x\^{}2) and 5\textasciitilde{}10 and a~b") == "(x^2) and 5~10 and a b"

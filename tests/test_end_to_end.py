"""The test that proves the product.

Build a paper that includes a matplotlib figure exported with the default
settings, compile it, and confirm the checker finds the defect that would
have caused IEEE to reject it.
"""

import shutil
from pathlib import Path

import pytest

from prarup.checks import run_all_checks
from prarup.compile import compile_pdf
from prarup.models import Rules

FIXTURES = Path(__file__).parent / "fixtures"

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

PAPER = r"""
\documentclass{article}
\usepackage{graphicx}
\begin{document}
\section{Results}
See Figure~\ref{fig:one}.
\begin{figure}[h]
  \centering
  \includegraphics[width=0.6\linewidth]{figure.pdf}
  \caption{A plot exported from matplotlib.}
  \label{fig:one}
\end{figure}
\end{document}
"""


@needs_tectonic
def test_a_paper_with_a_default_matplotlib_figure_is_rejected(tmp_path):
    """This is the whole product in one test."""
    shutil.copy(FIXTURES / "mpl_type3.pdf", tmp_path / "figure.pdf")
    (tmp_path / "paper.tex").write_text(PAPER)

    pdf, _ = compile_pdf(tmp_path / "paper.tex", tmp_path / "build")
    issues = run_all_checks(pdf, Rules())

    assert "FONT-02" in [i.code for i in issues], (
        "the Type3 font inside the included figure should have been found"
    )


@needs_tectonic
def test_the_same_paper_with_a_corrected_figure_passes(tmp_path):
    """Two lines of rcParams difference, and the paper is submittable."""
    shutil.copy(FIXTURES / "mpl_truetype.pdf", tmp_path / "figure.pdf")
    (tmp_path / "paper.tex").write_text(PAPER)

    pdf, _ = compile_pdf(tmp_path / "paper.tex", tmp_path / "build")
    issues = run_all_checks(pdf, Rules())

    assert [i.code for i in issues] == []


needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)


@needs_tectonic
@needs_pandoc
def test_docx_becomes_a_compliant_ieee_paper(tmp_path):
    """The full pipeline: .docx in, checked IEEE PDF out."""
    from prarup.checks import run_all_checks
    from prarup.convert import docx_to_tex
    from prarup.document import document_from_latex
    from prarup.models import Author, Rules
    from prarup.render import render

    fragment = docx_to_tex(FIXTURES / "sample.docx", tmp_path, standalone=False)
    document = document_from_latex(
        fragment.read_text(),
        authors=[Author("Krushna Parmar", "DA-IICT")],
        abstract="A short abstract.",
    )

    tex_path = tmp_path / "out.tex"
    tex_path.write_text(render(document))
    pdf, log = compile_pdf(tex_path, tmp_path)

    assert pdf.exists(), f"compilation failed:\n{log}"
    assert run_all_checks(pdf, Rules()) == []

    import pymupdf
    text = pymupdf.open(pdf)[0].get_text()
    # the abstract must precede the body, not be pushed down by a float
    assert text.index("Abstract") < text.index("Introduction")
    assert "Krushna Parmar" in text

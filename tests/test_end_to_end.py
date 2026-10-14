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


@pytest.mark.skipif(shutil.which("pandoc") is None or shutil.which("tectonic") is None,
                    reason="pandoc and tectonic needed")
def test_a_word_figure_wider_than_the_column_fails_the_build_and_fit_repairs_it(tmp_path):
    """The whole story: Word keeps the figure at 5.8 in, the IEEE column is
    3.5 in, Build reports the overlap, and Fit figures removes it."""
    import subprocess

    from prarup.gui import build_paper, fit_figures
    from prarup.models import Rules
    from test_measure import plot

    plot(tmp_path / "wide.png", 8)
    (tmp_path / "paper.md").write_text(
        "# Introduction\n\nSome text.\n\n![Accuracy](wide.png){width=5.8in}\n\n# Results\n\nMore.\n"
    )
    subprocess.run(["pandoc", "paper.md", "-o", "paper.docx"], cwd=tmp_path, check=True)

    _, issues = build_paper(tmp_path / "paper.docx", tmp_path / "build", "ieee", Rules())
    assert "GEOM-02" in [i.code for i in issues]

    report, issues = fit_figures(tmp_path / "paper.docx", tmp_path / "fit", "ieee", Rules())
    assert "GEOM-02" not in [i.code for i in issues]
    assert report.changes[0].double_after is True

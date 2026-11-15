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
def test_the_demo_paper_goes_from_unreadable_to_readable(tmp_path):
    """The demo: a Word figure 8 in wide squeezed into one column prints its
    10 pt labels at about 4 pt. Build says so; Fit figures fixes it."""
    from prarup.models import Rules
    from prarup.project import Project

    demo = tmp_path / "demo_paper.docx"
    shutil.copy(FIXTURES / "demo_paper.docx", demo)
    project = Project.open(demo)
    assert project.m.title == "Federated Learning on Drone Swarms"
    assert [a.name for a in project.m.authors] == ["Prateek Kalal", "Om Patel", "Krushna Parmar"]

    before = project.build(Rules())
    assert [i.code for i in before.issues] == ["GEOM-03"]

    [report] = project.fit(Rules())
    project.apply_fit(report)
    after = project.build(Rules())
    assert after.issues == []
    assert report.changes[0].text_after >= 7


@needs_tectonic
@needs_pandoc
def test_the_abstract_comes_before_the_body(tmp_path):
    import pymupdf
    from prarup.models import Rules
    from prarup.project import Project

    demo = tmp_path / "demo_paper.docx"
    shutil.copy(FIXTURES / "demo_paper.docx", demo)
    result = Project.open(demo).build(Rules())
    text = pymupdf.open(result.pdf)[0].get_text()
    assert text.index("Abstract") < text.index("Introduction")

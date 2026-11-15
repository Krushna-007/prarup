"""Writing a Manuscript as an IEEE paper, and compiling it.

Every real paper must compile, and the PDF must carry what the source had.
Before the redesign, none of the three Word papers compiled.
"""

import shutil
from pathlib import Path

import pymupdf
import pytest

from prarup.compile import compile_pdf
from prarup.ingest import open_paper
from prarup.renderer import _lines, _unwrap_environments, render

REAL = Path(__file__).parent / "fixtures" / "real"
LATEX = Path(__file__).parent / "fixtures" / "latex_project" / "main.tex"

needs_tools = pytest.mark.skipif(
    shutil.which("pandoc") is None or shutil.which("tectonic") is None,
    reason="pandoc and tectonic needed",
)


def build(source: Path, project: Path):
    m = open_paper(source, project)
    tex = project / "paper.tex"
    tex.write_text(render(m, project))
    pdf, log = compile_pdf(tex, project / "build")
    assert pdf.exists(), log[-2000:]
    return m, tex.read_text(), pymupdf.open(pdf)


@needs_tools
@pytest.mark.parametrize("name", ["yolo_football", "uav_imagery", "svm_diabetes"])
def test_every_real_word_paper_compiles(name, tmp_path):
    m, tex, pdf = build(REAL / f"{name}.docx", tmp_path)
    text = " ".join(page.get_text() for page in pdf)
    assert " ".join(m.title.split()[:4]) in " ".join(text.split())
    assert "longtable" not in tex                    # illegal in two columns


@needs_tools
def test_the_latex_project_compiles_despite_pdflatex_only_packages(tmp_path):
    m, tex, pdf = build(LATEX, tmp_path)
    assert "inputenc" not in tex
    assert r"\mathds" in tex and r"\usepackage{dsfont}" in tex
    text = pdf[0].get_text()
    assert "Federated Learning on Drone Swarms" in text
    assert "Asha Rao" in text


@needs_tools
def test_a_missing_image_is_a_visible_placeholder_not_a_crash(tmp_path):
    _, tex, pdf = build(LATEX, tmp_path)
    assert "image missing" in tex
    assert "image missing" in " ".join(p.get_text() for p in pdf)


@needs_tools
def test_a_wide_text_table_spans_both_columns(tmp_path):
    _, tex, _ = build(REAL / "yolo_football.docx", tmp_path)
    assert r"\begin{table*}" in tex and r"\begin{tabularx}{\textwidth}" in tex


@needs_tools
def test_captions_detected_in_word_reach_the_pdf(tmp_path):
    _, _, pdf = build(REAL / "svm_diabetes.docx", tmp_path)
    text = " ".join(" ".join(p.get_text() for p in pdf).split())
    assert "Fig. 2. SVM technique" in text
    assert "Attributes of dataset" in text


def test_align_inside_display_maths_is_unwrapped_and_keeps_its_label():
    latex = "\\[\\label{eq:b}\n\\begin{align}\na &= b \\label{eq:a}\\\\\nc &= d\n\\end{align}\\]"
    out = _unwrap_environments(latex)
    assert not out.startswith("\\[")
    assert out.count("\\label") == 2
    assert "c &= d\\label{eq:b}" in out           # on the line without a label


def test_long_affiliations_break_at_commas():
    out = _lines("Department of Computer Science, College of Science, Nawroz University, Iraq")
    assert out.count("\\\\") >= 1
    assert all(len(line.strip(" \\")) <= 45 for line in out.split("\n"))

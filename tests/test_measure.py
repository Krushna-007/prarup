"""Measuring figures in a real compiled PDF.

The expected numbers are worked out by hand: a plot drawn with 10 pt
text on an 8 inch canvas, printed 4 inches wide, carries 5 pt text.
"""

import shutil

import pytest

from prarup.compile import compile_pdf
from prarup.figures import find_graphics, instrument
from prarup.measure import measure, small_text

needs_tools = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)
needs_ocr = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract not installed"
)


def plot(path, width_in, fonttype=42, dpi=150, text_pt=10, height_in=3):
    """A plot whose text is all text_pt on a canvas width_in inches wide."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["pdf.fonttype"] = fonttype
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.plot([0, 1, 2, 3], [1, 3, 2, 4])
    ax.set_xlabel("communication round", fontsize=text_pt)
    ax.set_ylabel("accuracy", fontsize=text_pt)
    ax.set_title("Training accuracy per round", fontsize=text_pt)
    ax.tick_params(labelsize=text_pt)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


PAPER = r"""\documentclass[conference]{IEEEtran}
\usepackage{graphicx}
\begin{document}
Some text in the first column.
\begin{figure}
\centering
\includegraphics[width=%(width)s]{%(file)s}
\caption{A figure}
\end{figure}
\end{document}
"""


def build(tmp_path, file, width):
    tex = PAPER % {"width": width, "file": file}
    source = tmp_path / "paper.tex"
    source.write_text(instrument(tex))
    pdf, log = compile_pdf(source, tmp_path / "out")
    assert pdf.exists(), log
    return measure(pdf, find_graphics(tex), tmp_path)


@needs_tools
def test_geometry_comes_from_latex(tmp_path):
    plot(tmp_path / "fig.pdf", 6)
    geometry, _ = build(tmp_path, "fig.pdf", "2in")
    assert geometry.column == pytest.approx(252, abs=1)    # IEEEtran conference
    assert geometry.text == pytest.approx(516, abs=1)


@needs_tools
def test_vector_text_size_is_measured_exactly(tmp_path):
    plot(tmp_path / "fig.pdf", 6)
    _, [m] = build(tmp_path, "fig.pdf", "2in")
    assert m.text_source == "vector"
    assert m.text_pt == pytest.approx(10 * 2 / 6, abs=0.1)   # 3.33 pt


@needs_tools
def test_a_figure_inside_its_column_does_not_overflow(tmp_path):
    plot(tmp_path / "fig.pdf", 6)
    _, [m] = build(tmp_path, "fig.pdf", "3in")
    assert m.overflow == 0


@needs_tools
def test_a_figure_wider_than_its_column_overflows(tmp_path):
    """The case pandoc produces from a Word file: a fixed size in inches."""
    plot(tmp_path / "fig.pdf", 6)
    _, [m] = build(tmp_path, "fig.pdf", "5.8in")
    assert m.overflow == pytest.approx(5.8 * 72 - 252, abs=3)


@needs_tools
@needs_ocr
def test_bitmap_text_size_is_read_with_ocr(tmp_path):
    plot(tmp_path / "fig.png", 8)
    _, [m] = build(tmp_path, "fig.png", "4in")
    assert m.text_source == "ocr"
    assert m.text_pt == pytest.approx(10 * 4 / 8, abs=0.7)    # 5 pt


def test_small_text_ignores_one_tiny_glyph():
    assert small_text([2.0, 8.0, 8.0, 8.0, 9.0, 9.0]) == 8.0


def test_small_text_with_nothing_measured():
    assert small_text([]) is None

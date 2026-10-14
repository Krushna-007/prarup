"""Finding and resizing figures in LaTeX source. Pure string work."""

from prarup.figures import (
    find_graphics,
    instrument,
    resize,
    set_width,
)

PANDOC_FIGURE = r"""
\begin{figure}[htbp]
\centering
\includegraphics[width=5.83333in,height=2.1875in,alt={Accuracy}]{media/rId9.png}
\caption{Accuracy over rounds}
\end{figure}
"""

TWO_FIGURES = r"""
\begin{figure}
\includegraphics[width=0.9\columnwidth]{a.pdf}
\caption{A}
\end{figure}
Text.
\begin{figure*}
\includegraphics{b}
\caption{B}
\end{figure*}
"""


def test_finds_a_graphic_with_its_path_and_options():
    [g] = find_graphics(PANDOC_FIGURE)
    assert g.path == "media/rId9.png"
    assert "width=5.83333in" in g.options
    assert g.env == "figure"


def test_numbers_graphics_in_order_and_knows_figure_star():
    a, b = find_graphics(TWO_FIGURES)
    assert (a.index, a.env) == (1, "figure")
    assert (b.index, b.env, b.options) == (2, "figure*", "")


def test_a_lone_graphic_in_a_figure_can_be_resized():
    assert find_graphics(PANDOC_FIGURE)[0].reason == ""


def test_subfigures_are_left_alone():
    """Each panel's width is relative to its own box. Resizing one breaks the set."""
    tex = r"""
\begin{figure}
\begin{subfigure}{0.45\columnwidth}\includegraphics[width=\linewidth]{a}\end{subfigure}
\begin{subfigure}{0.45\columnwidth}\includegraphics[width=\linewidth]{b}\end{subfigure}
\caption{Pair}
\end{figure}
"""
    graphics = find_graphics(tex)
    assert len(graphics) == 2
    assert all("more than one graphic" in g.reason for g in graphics)


def test_graphic_outside_a_figure_is_left_alone():
    [g] = find_graphics(r"Inline \includegraphics{logo.png} here.")
    assert g.env == ""
    assert "not inside a figure" in g.reason


def test_rotated_graphic_is_left_alone():
    tex = "\\begin{figure}\\includegraphics[angle=90,width=3in]{a}\\end{figure}"
    assert "rotated" in find_graphics(tex)[0].reason


def test_scaled_box_is_left_alone():
    tex = "\\begin{figure}\\resizebox{\\columnwidth}{!}{\\includegraphics{a}}\\end{figure}"
    assert "resizebox" in find_graphics(tex)[0].reason


def test_commented_out_graphics_are_ignored():
    tex = "% \\includegraphics{old.png}\n\\begin{figure}\\includegraphics{new.png}\\end{figure}"
    assert [g.path for g in find_graphics(tex)] == ["new.png"]


def test_escaped_percent_is_not_a_comment():
    tex = "50\\% done \\begin{figure}\\includegraphics{a.png}\\end{figure}"
    assert len(find_graphics(tex)) == 1


def test_set_width_replaces_every_size_key_and_keeps_the_rest():
    options = "width=5.83333in,height=2.1875in,alt={Accuracy, final},keepaspectratio"
    assert set_width(options, r"0.95\columnwidth") == (
        r"alt={Accuracy, final},width=0.95\columnwidth"
    )


def test_set_width_on_empty_options():
    assert set_width("", r"1\textwidth") == r"width=1\textwidth"


def test_resize_changes_only_the_named_graphic():
    out = resize(TWO_FIGURES, {1: (r"0.5\columnwidth", False)})
    assert r"\includegraphics[width=0.5\columnwidth]{a.pdf}" in out
    assert r"\includegraphics{b}" in out


def test_resize_can_move_a_figure_across_both_columns():
    out = resize(PANDOC_FIGURE, {1: (r"0.8\textwidth", True)})
    assert r"\begin{figure*}[htbp]" in out
    assert r"\end{figure*}" in out
    assert r"width=0.8\textwidth" in out


def test_resize_leaves_other_figures_environments_alone():
    out = resize(TWO_FIGURES, {1: (r"0.9\textwidth", True)})
    assert out.count(r"\begin{figure*}") == 2
    assert out.count(r"\end{figure*}") == 2
    assert r"\begin{figure}" not in out


def test_instrument_wraps_every_graphic_and_adds_the_hook():
    tex = "\\documentclass{IEEEtran}\n\\begin{document}\n" + TWO_FIGURES + "\\end{document}\n"
    out = instrument(tex)
    assert r"\prarupfig{1}{\includegraphics[width=0.9\columnwidth]{a.pdf}}" in out
    assert r"\prarupfig{2}{\includegraphics{b}}" in out
    assert out.index("PrarupGeometry") < out.index(r"\begin{document}")

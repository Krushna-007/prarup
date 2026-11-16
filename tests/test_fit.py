import shutil

import pytest

from prarup.fit import describe, fit_paper
from prarup.models import Rules
from test_measure import plot

pytestmark = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

COLUMN, TEXT = 252, 516


def paper(tmp_path, figures, filler=1):
    body = "\n".join(
        "\\begin{figure}[htbp]\n\\centering\n"
        f"\\includegraphics[width={width}]{{{name}}}\n"
        f"\\caption{{Figure {n}}}\n\\end{{figure}}\n" + "Body text. " * 80
        for n, (name, width) in enumerate(figures, start=1)
    )
    tex = tmp_path / "paper.tex"
    tex.write_text(
        "\\documentclass[conference]{IEEEtran}\n\\usepackage{graphicx}\n"
        "\\begin{document}\n" + ("Opening text. " * 150 + "\n\n") * filler
        + body + "\n\\end{document}\n"
    )
    return tex


def test_an_overflowing_figure_with_large_text_shrinks_into_its_column(tmp_path):
    plot(tmp_path / "fig.pdf", 4)
    tex = paper(tmp_path, [("fig.pdf", "5in")])

    [c] = fit_paper(tex, tmp_path / "out", Rules(page_limit=6)).changes

    assert c.overflow_before > 0
    assert c.double_after is False
    assert c.width_after == pytest.approx(COLUMN, abs=1)
    assert c.text_after == pytest.approx(8.75, abs=0.2)


def test_a_wide_plot_moves_across_both_columns_to_stay_readable(tmp_path):
    plot(tmp_path / "fig.pdf", 8)
    tex = paper(tmp_path, [("fig.pdf", "5.8in")])

    [c] = fit_paper(tex, tmp_path / "out", Rules(page_limit=6)).changes

    assert c.double_after is True
    assert c.text_after >= 7
    assert c.width_after <= TEXT + 1


def test_text_too_small_even_at_full_width_is_reported_not_hidden(tmp_path):
    plot(tmp_path / "fig.pdf", 20)
    tex = paper(tmp_path, [("fig.pdf", "5in")])

    [c] = fit_paper(tex, tmp_path / "out", Rules(page_limit=6)).changes

    assert "re-export" in c.note
    assert c.width_after <= COLUMN + 1


def test_figures_shrink_together_to_meet_the_page_limit(tmp_path):
    for n in range(6):
        plot(tmp_path / f"f{n}.pdf", 3, text_pt=20, height_in=3)
    figures = [(f"f{n}.pdf", r"\columnwidth") for n in range(6)]

    full = fit_paper(paper(tmp_path, figures), tmp_path / "full", Rules(page_limit=9))
    limit = full.pages_after - 1
    report = fit_paper(paper(tmp_path, figures), tmp_path / "out", Rules(page_limit=limit))

    assert report.pages_after <= limit
    assert all(c.text_after >= 7 - 0.1 for c in report.changes)
    assert not report.summary


def test_when_it_cannot_fit_it_says_how_much_to_cut(tmp_path):
    plot(tmp_path / "fig.pdf", 3)
    tex = paper(tmp_path, [("fig.pdf", r"\columnwidth")], filler=8)

    report = fit_paper(tex, tmp_path / "out", Rules(page_limit=1))

    assert "pages over" in report.summary
    assert report.changes[0].text_after >= 7 - 0.1


def test_the_original_is_untouched_and_the_result_sits_beside_it(tmp_path):
    plot(tmp_path / "fig.pdf", 4)
    tex = paper(tmp_path, [("fig.pdf", "5in")])
    original = tex.read_text()

    report = fit_paper(tex, tmp_path / "out", Rules(page_limit=6))

    assert tex.read_text() == original
    assert report.fitted_tex == tmp_path / "paper-fitted.tex"
    assert report.pdf.exists()
    assert sorted(p.name for p in tmp_path.glob("*.tex")) == ["paper-fitted.tex", "paper.tex"]


def test_the_report_reads_as_sentences(tmp_path):
    plot(tmp_path / "fig.pdf", 4)
    report = fit_paper(paper(tmp_path, [("fig.pdf", "5in")]), tmp_path / "out", Rules())
    lines = describe(report)
    assert lines[0].startswith("Fig. 1 (page")
    assert "past its column" in lines[0]
    assert lines[-1].startswith("Pages:")


def test_a_figure_that_already_fits_is_left_exactly_as_written(tmp_path):
    plot(tmp_path / "fig.pdf", 3)
    tex = paper(tmp_path, [("fig.pdf", r"\columnwidth")])

    report = fit_paper(tex, tmp_path / "out", Rules(page_limit=6))

    assert r"\includegraphics[width=\columnwidth]{fig.pdf}" in report.fitted_tex.read_text()
    assert describe(report)[0].startswith("Fig. 1 (page 1): unchanged")

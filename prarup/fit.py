"""The figure fitter: compile, measure, resize, compile again.

Every figure gets the largest width that stays inside its column. If that
leaves its text below the readable minimum, it moves across both columns.
If the paper is then over the page limit, figures with readable text to
spare are shrunk together, searching by halves, until it fits or every
figure is at its smallest readable size. Nothing is ever shrunk below
that size: the report says how much to cut instead.

The author's file is never changed. The result is <name>-fitted.tex,
written beside it so its relative image paths still resolve.
"""

import math
from pathlib import Path

import pymupdf

from prarup.compile import compile_pdf
from prarup.figures import find_graphics, instrument, resize
from prarup.measure import measure
from prarup.models import FigureChange, FitReport, Rules

SEARCH_STEPS = 5     # 2^5 = 32 steps between full size and the smallest readable

# LaTeX's measured box comes out about a point narrower than the width it
# was given. Differences this small are rounding, not a change worth making.
SLACK = 2.0


class FitFailed(Exception):
    """Raised when the paper cannot be compiled or measured."""


def _compile(tex: str, name: str, source: Path, out_dir: Path) -> Path:
    """Compile a variant of the paper, written beside the original."""
    path = source.with_name(name)
    path.write_text(tex)
    try:
        pdf, log = compile_pdf(path, out_dir)
    finally:
        path.unlink(missing_ok=True)
    if not pdf.exists():
        raise FitFailed(log or "compilation produced no PDF")
    return pdf


def _pages(pdf: Path) -> int:
    with pymupdf.open(pdf) as doc:
        return doc.page_count


def _last_page_fill(pdf: Path) -> float:
    """How far down the last page the content reaches, 0 to 1."""
    with pymupdf.open(pdf) as doc:
        page = doc[-1]
        bottoms = [b[3] for b in page.get_text("blocks")]
        bottoms += [r.y1 for img in page.get_images() for r in page.get_image_rects(img[0])]
        return min(1.0, max(bottoms, default=0) / page.rect.height)


def _width_expr(width: float, double: bool, geometry) -> str:
    """Width as a fraction of the column or text width, rounded down."""
    base, name = (geometry.text, r"\textwidth") if double else (geometry.column, r"\columnwidth")
    return f"{math.floor(width / base * 1000) / 1000:g}{name}"


def plan(graphic, m, geometry, min_pt: float):
    """(width, double, smallest_width, note) for one measured graphic."""
    double = graphic.env == "figure*"
    k = m.text_per_width
    smallest = min_pt / k if k else None

    if smallest is not None and smallest > geometry.text:
        widest = geometry.text if double else geometry.column
        return (min(m.width, widest), double, min(m.width, widest),
                f"text is {k * geometry.text:.1f} pt even at full page width; "
                f"re-export it with larger fonts")
    if smallest is not None and smallest > geometry.column:
        double = True
    widest = geometry.text if double else geometry.column
    if abs(m.width - widest) < SLACK:
        widest = m.width            # already full width; keep it exactly
    floor = smallest if smallest is not None else min(m.width, widest)
    note = "" if k else "no text found to measure, so it is only kept inside its column"
    return max(floor, min(m.width, widest)), double, floor, note


def fit_paper(source: Path, out_dir: Path, rules: Rules) -> FitReport:
    """Fit the figures of a .tex paper and return what changed."""
    tex = source.read_text()
    graphics = find_graphics(tex)
    if not graphics:
        raise FitFailed("the paper has no \\includegraphics to fit")

    stem = source.stem
    measured_pdf = _compile(instrument(tex), f"{stem}-prarup-measure.tex", source, out_dir)
    geometry, measured = measure(measured_pdf, graphics, source.parent)
    if geometry is None:
        raise FitFailed("could not read the page geometry from the compiled PDF")
    pages_before = _pages(measured_pdf)
    by_index = {m.index: m for m in measured}

    targets, floors, changes = {}, {}, []
    for g in graphics:
        m = by_index.get(g.index)
        if m is None:
            continue
        change = FigureChange(g.index, m.page, m.width, m.width, g.env == "figure*",
                              g.env == "figure*", m.overflow, m.text_pt, m.text_pt)
        if g.reason:
            change.note = f"left alone because {g.reason}"
        else:
            width, double, floor, change.note = plan(g, m, geometry, rules.min_figure_text_pt)
            targets[g.index] = (width, double)
            floors[g.index] = floor
        changes.append(change)

    def layout(t: float) -> dict:
        """Every figure at t of the way from its smallest readable width to its target.

        A figure that would end up where it started is left out, so the
        author's own \\includegraphics stays exactly as written.
        """
        sizes = {}
        for i, (w, d) in targets.items():
            width = floors[i] + t * (w - floors[i])
            if abs(width - by_index[i].width) >= SLACK or d != (graphics[i - 1].env == "figure*"):
                sizes[i] = (_width_expr(width, d, geometry), d)
        return sizes

    def pages_at(t: float) -> int:
        return _pages(_compile(resize(tex, layout(t)), f"{stem}-prarup-try.tex", source, out_dir))

    best, summary = 1.0, ""
    pages = pages_at(1.0)
    if pages > rules.page_limit and targets:
        smallest_pdf = _compile(resize(tex, layout(0.0)), f"{stem}-prarup-try.tex", source, out_dir)
        if _pages(smallest_pdf) > rules.page_limit:
            over = _pages(smallest_pdf) - rules.page_limit - 1 + _last_page_fill(smallest_pdf)
            summary = (f"Still about {over:.1f} pages over the {rules.page_limit}-page limit with "
                       f"every figure at its smallest readable size. Cut text or figures; "
                       f"shrinking further would make figure text smaller than "
                       f"{rules.min_figure_text_pt:g} pt.")
        else:
            low, high = 0.0, 1.0                 # low always fits, high does not
            for _ in range(SEARCH_STEPS):
                middle = (low + high) / 2
                low, high = (middle, high) if pages_at(middle) <= rules.page_limit else (low, middle)
            best = low

    fitted = resize(tex, layout(best))
    fitted_tex = source.with_name(f"{stem}-fitted.tex")
    fitted_tex.write_text(fitted)

    # measure the result rather than trusting the arithmetic
    check_pdf = _compile(instrument(fitted), f"{stem}-prarup-measure.tex", source, out_dir)
    _, after = measure(check_pdf, find_graphics(fitted), source.parent)
    after = {m.index: m for m in after}
    for change in changes:
        m = after.get(change.index)
        if m is None:
            continue
        change.width_after, change.text_after = m.width, m.text_pt
        change.double_after = targets.get(change.index, (0, change.double_before))[1]
        change.page = m.page
        if m.overflow >= 1 and not change.note:
            change.note = f"still {m.overflow:.0f} pt past its column"

    pdf, log = compile_pdf(fitted_tex, out_dir)
    if not pdf.exists():
        raise FitFailed(log or "the fitted paper did not compile")
    return FitReport(changes, pages_before, _pages(pdf), rules.page_limit,
                     fitted_tex, pdf, summary)


def _size(points: float) -> str:
    return f"{points / 72:.2f} in"


def describe(report: FitReport) -> list[str]:
    """The report as lines a person reads top down."""
    lines = []
    for c in report.changes:
        span = lambda double: "both columns" if double else "one column"
        text = lambda pt: "text not measured" if pt is None else f"text {pt:.1f} pt"
        moved = (abs(c.width_after - c.width_before) >= SLACK
                 or c.double_after != c.double_before)
        head = f"Fig. {c.index} (page {c.page}): "
        if moved:
            line = (head + f"{_size(c.width_before)}, {span(c.double_before)}, {text(c.text_before)}"
                    f"  ->  {_size(c.width_after)}, {span(c.double_after)}, {text(c.text_after)}")
            if c.overflow_before >= 1:
                line += f"  (was {c.overflow_before:.0f} pt past its column)"
        else:
            line = head + f"unchanged, {_size(c.width_after)}, {text(c.text_after)}"
        if c.note:
            line += f"  [{c.note}]"
        lines.append(line)

    lines.append(f"Pages: {report.pages_before} -> {report.pages_after} "
                 f"(limit {report.page_limit})")
    if report.summary:
        lines.append(report.summary)
    return lines

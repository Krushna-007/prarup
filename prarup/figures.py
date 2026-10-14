"""Find and resize figures in LaTeX source.

Pure string work: no files, no processes. The fitter decides the sizes;
this file only knows how to read and write them safely.
"""

import re

from prarup.models import Graphic

_GRAPHIC = re.compile(r"\\includegraphics\s*(?:\[(?P<options>[^\]]*)\])?\s*\{(?P<path>[^}]*)\}")
_ENV = re.compile(r"\\(?P<kind>begin|end)\{(?P<name>figure\*?)\}")

# Inside any of these, a graphic's width is relative to something other
# than the column, so changing it can break the layout around it.
_NESTED_BOXES = ["subfigure", "subfloat", "minipage", "tabular", "resizebox", "scalebox", "adjustbox"]

_SIZE_KEYS = {"width", "height", "totalheight", "scale", "keepaspectratio"}

MEASURE_HOOK = r"""%% Added by Prarup to measure figures. Not part of the paper.
\AtBeginDocument{\special{pdf:docinfo << /PrarupGeometry (\the\columnwidth\space\the\textwidth\space\the\dimexpr1in+\hoffset+\oddsidemargin\relax\space\the\columnsep) >>}}
\newcommand\prarupfig[2]{\special{pdf:bann << /Type /Annot /Subtype /Link /Border [0 0 0] /A << /S /URI /URI (prarup:fig:#1) >> >>}#2\special{pdf:eann}}
"""


def _comment_spans(tex: str) -> list[tuple[int, int]]:
    """Every unescaped % to the end of its line."""
    return [m.span() for m in re.finditer(r"(?<!\\)%[^\n]*", tex)]


def _in_any(pos: int, spans) -> bool:
    return any(start <= pos < end for start, end in spans)


def _figure_envs(tex: str, comments) -> list[tuple]:
    """(name, begin_span, end_span) for every figure and figure* environment."""
    envs, open_ = [], []
    for m in _ENV.finditer(tex):
        if _in_any(m.start(), comments):
            continue
        if m.group("kind") == "begin":
            open_.append((m.group("name"), m.span()))
        elif open_:
            name, begin = open_.pop()
            envs.append((name, begin, m.span()))
    return envs


def find_graphics(tex: str) -> list[Graphic]:
    """Every \\includegraphics outside comments, in source order.

    Each one says which float it sits in and, when it must not be
    resized, why. Only a lone graphic directly inside a figure is safe.
    """
    comments = _comment_spans(tex)
    envs = _figure_envs(tex, comments)
    matches = [m for m in _GRAPHIC.finditer(tex) if not _in_any(m.start(), comments)]

    graphics = []
    for number, m in enumerate(matches, start=1):
        g = Graphic(index=number, start=m.start(), end=m.end(),
                    options=(m.group("options") or "").strip(),
                    path=m.group("path").strip())

        inside = [e for e in envs if e[1][1] <= m.start() and m.end() <= e[2][0]]
        if inside:
            g.env, g.env_begin, g.env_end = max(inside, key=lambda e: e[1][0])
            body = tex[g.env_begin[1]:g.env_end[0]]
            siblings = [o for o in matches if g.env_begin[1] <= o.start() < g.env_end[0]]
            nested = [box for box in _NESTED_BOXES if box in body]
            if len(siblings) > 1:
                g.reason = "the figure has more than one graphic"
            elif nested:
                g.reason = f"it sits inside {nested[0]}"
        else:
            g.reason = "it is not inside a figure environment"

        if not g.reason and re.search(r"\b(angle|origin)\s*=", g.options):
            g.reason = "it is rotated"
        graphics.append(g)
    return graphics


def _split_options(options: str) -> list[str]:
    """Split key=value pairs on commas that are not inside braces."""
    parts, depth, current = [], 0, ""
    for char in options:
        depth += (char == "{") - (char == "}")
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return [p.strip() for p in parts if p.strip()]


def set_width(options: str, width: str) -> str:
    """Drop every size key and set a single width. Other keys are kept."""
    kept = [p for p in _split_options(options) if p.split("=")[0].strip() not in _SIZE_KEYS]
    return ",".join(kept + [f"width={width}"])


def resize(tex: str, changes: dict) -> str:
    """Apply {index: (width, double_column)} to the source.

    Edits are applied from the end of the file backwards so the spans
    found earlier stay valid.
    """
    edits = []   # (start, end, replacement)
    for g in find_graphics(tex):
        if g.index not in changes:
            continue
        width, double = changes[g.index]
        edits.append((g.start, g.end, f"\\includegraphics[{set_width(g.options, width)}]{{{g.path}}}"))
        wanted = "figure*" if double else "figure"
        if g.env and g.env != wanted:
            edits.append((*g.env_begin, f"\\begin{{{wanted}}}"))
            edits.append((*g.env_end, f"\\end{{{wanted}}}"))

    for start, end, text in sorted(edits, reverse=True):
        tex = tex[:start] + text + tex[end:]
    return tex


def instrument(tex: str) -> str:
    """A copy that reports the page geometry and every graphic's box.

    The boxes come back as invisible links named prarup:fig:N, which
    PyMuPDF reads with their exact rectangles. Used only for measuring;
    the paper itself is never built from this copy.
    """
    if r"\begin{document}" not in tex:
        raise ValueError("no \\begin{document} found")

    for g in sorted(find_graphics(tex), key=lambda g: g.start, reverse=True):
        tex = tex[:g.start] + f"\\prarupfig{{{g.index}}}{{{tex[g.start:g.end]}}}" + tex[g.end:]

    return tex.replace(r"\begin{document}", MEASURE_HOOK + r"\begin{document}", 1)

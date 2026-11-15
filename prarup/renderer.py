"""Write a Manuscript as an IEEE conference paper in LaTeX.

Prarup writes the figures, tables, equations, headings and references
itself, so it controls exactly what LaTeX receives: a table becomes a
plain tabular (pandoc's longtable cannot be used in two columns), a
missing image becomes a visible placeholder rather than a crash. Running
text goes through pandoc, untouched unless the user edited it.

Every pandoc conversion is batched into a few runs.
"""

import re
from pathlib import Path

import jinja2

from prarup import pandoc
from prarup.manuscript import Manuscript

TEMPLATES = Path(__file__).parent / "templates"
BITMAPS_TEX_READS = {".png", ".jpg", ".jpeg", ".pdf"}
_NUMBERING = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVX]+\.|[A-Z]\.)\s+(?=\S)")
_UNNUMBERED = re.compile(r"^\s*(acknowledge?ments?|appendix)\s*$", re.I)
_ALIGN = {"AlignLeft": "l", "AlignRight": "r", "AlignCenter": "c", "AlignDefault": "l"}


def _env() -> jinja2.Environment:
    return jinja2.Environment(
        block_start_string=r"\BLOCK{", block_end_string="}",
        variable_start_string=r"\VAR{", variable_end_string="}",
        comment_start_string=r"\#{", comment_end_string="}",
        trim_blocks=True, lstrip_blocks=True, autoescape=False,
        keep_trailing_newline=True, loader=jinja2.FileSystemLoader(TEMPLATES),
    )


def _plain_heading(markdown: str) -> str:
    """Heading text without Word's own numbering: IEEE numbers sections itself."""
    return _NUMBERING.sub("", markdown.replace("\\.", ".")).strip()


def _flatten_tables(blocks: list) -> list:
    """A table inside a table cell becomes its text: tabular cannot nest a longtable."""
    out = []
    for b in blocks:
        if b.get("t") == "Table":
            out.append({"t": "Plain", "c": [{"t": "Str", "c": pandoc.stringify(b).replace("\n", "; ")}]})
        else:
            out.append(b)
    return out


def _bounded(blocks: list) -> list:
    """Images inside running text lose Word's fixed size, so pandoc scales them
    to fit the column instead of running across the next one."""
    import copy
    blocks = copy.deepcopy(blocks)

    def walk(n):
        if isinstance(n, dict):
            if n.get("t") == "Image":
                n["c"][0][2] = [kv for kv in n["c"][0][2] if kv[0] not in ("width", "height")]
            else:
                walk(n.get("c"))
        elif isinstance(n, list):
            for item in n:
                walk(item)
    walk(blocks)
    return blocks


def _cells(table: dict) -> list[list[tuple]]:
    """Rows of (alignment, colspan, blocks) from a pandoc Table node."""
    _, _, _, head, bodies, foot = table["c"]
    rows = list(head[1])
    for body in bodies:
        rows += body[2] + body[3]
    rows += foot[1]
    return [[(cell[1]["t"], cell[3], cell[4]) for cell in row[1]] for row in rows], len(head[1])


def _table_latex(block, caption: str, rows: list, header_rows: int,
                 cell_latex: dict, columns: list) -> str:
    width = max((sum(span for _, span, _ in r) for r in rows), default=1)
    longest = [0] * width                    # characters in each column's longest cell
    for r in rows:
        col = 0
        for n, (_, span, _) in enumerate(r):
            if span == 1 and col < width:
                longest[col] = max(longest[col], len(re.sub(r"\\[a-z]+|[{}]", "", cell_latex.get((id(r), n), ""))))
            col += span
    # Footnote-size text runs about 4.5 pt per character. A table wider than
    # its column wraps its text columns; much wider, it spans both columns.
    natural = sum(min(n, 60) for n in longest) * 4.5 + 12 * width
    double = natural > 252 * 1.6
    wrap_text = natural > 252 * 0.95
    long_cols = {c for c, n in enumerate(longest) if wrap_text and n > 10}
    wrap = r">{\raggedright\arraybackslash}X"           # long text wraps instead of overflowing
    spec = "".join(wrap if c in long_cols else (columns[c] if c < len(columns) else "l")
                   for c in range(width))
    span_width = r"\textwidth" if double else r"\columnwidth"

    lines = []
    for number, r in enumerate(rows):
        cells = []
        for n, (align, span, _) in enumerate(r):
            text = cell_latex.get((id(r), n), "").replace("\n\n", " \\newline ")
            if span > 1:
                text = f"\\multicolumn{{{span}}}{{{_ALIGN.get(align, 'l')}}}{{{text}}}"
            cells.append(text)
        lines.append(" & ".join(cells) + r" \\")
        if number == header_rows - 1:
            lines.append(r"\midrule")
    body = "\n".join(lines)
    if long_cols:
        inner = (f"\\begin{{tabularx}}{{{span_width}}}{{{spec}}}\n\\toprule\n{body}\n"
                 f"\\bottomrule\n\\end{{tabularx}}")
    else:
        inner = (f"\\begin{{adjustbox}}{{max width={span_width}}}\n\\begin{{tabular}}{{{spec}}}\n"
                 f"\\toprule\n{body}\n\\bottomrule\n\\end{{tabular}}\n\\end{{adjustbox}}")
    label = f"\\label{{{block.label}}}" if block.label else ""
    cap = f"\\caption{{{caption}}}{label}\n" if caption else ""
    env = "table*" if double else "table"
    return f"\\begin{{{env}}}[htbp]\n\\centering\n\\footnotesize\n{cap}{inner}\n\\end{{{env}}}"


def _figure_latex(block, caption: str, project: Path) -> str:
    parts = []
    share = 0.98 / max(1, len(block.images))
    base = r"\textwidth" if block.double else r"\columnwidth"
    for path in block.images or [""]:
        file = project / path if path else None
        if file and file.is_file() and file.suffix.lower() in BITMAPS_TEX_READS:
            width = block.fit_width if block.fit_width and len(block.images) == 1 else f"{share:.2f}{base}"
            parts.append(f"\\includegraphics[width={width}]{{{path}}}")
        else:
            why = "image missing" if not path or not (file and file.is_file()) else \
                f"{file.suffix} cannot be placed; replace it with PNG or PDF"
            name = Path(path).name.replace("_", r"\_") if path else "no image"
            parts.append(f"\\fbox{{\\parbox[c][1.2in][c]{{{share * 0.9:.2f}\\columnwidth}}"
                         f"{{\\centering\\footnotesize\\textbf{{{why}}}\\\\{name}}}}}")
    label = f"\\label{{{block.label}}}" if block.label else ""
    cap = f"\\caption{{{caption}}}{label}\n" if caption else ""
    env = "figure*" if block.double else "figure"
    return (f"\\begin{{{env}}}[htbp]\n\\centering\n" + "\\hfill\n".join(parts) + "\n" + cap
            + f"\\end{{{env}}}")


def _references_latex(m: Manuscript, block, entries_latex: list[str]) -> str:
    if m.bibliography:
        return "\\bibliographystyle{IEEEtran}\n\\bibliography{" + Path(m.bibliography).stem + "}"
    if not entries_latex:
        return ""
    keys = block.keys or [f"ref{n}" for n in range(1, len(entries_latex) + 1)]
    items = "\n".join(f"\\bibitem{{{k}}} {re.sub(r'^\\s*\\[\\d+\\]\\s*', '', e)}"
                      for k, e in zip(keys, entries_latex))
    return f"\\begin{{thebibliography}}{{{len(entries_latex)}}}\n{items}\n\\end{{thebibliography}}"


def body_latex(m: Manuscript, project: Path) -> str:
    """The paper's body as LaTeX, ready for the template."""
    # 1. everything that needs pandoc, collected for batched runs
    edited = [b for b in m.blocks if b.edited and b.kind in ("para", "quote", "list", "code")]
    parsed = dict(zip((b.id for b in edited),
                      pandoc.markdown_to_blocks([b.text for b in edited], m.api)))
    short = []        # headings, captions and reference entries: Markdown -> LaTeX
    for b in m.blocks:
        if b.kind == "heading":
            short.append(_plain_heading(b.text))
        elif b.kind in ("figure", "table"):
            short.append(b.caption)
        elif b.kind == "references":
            short += b.entries
    short_latex = iter(pandoc.markdown_to_latex(short))

    cell_pieces, cell_keys, columns, table_rows = [], [], {}, {}
    for b in m.tables():
        if not b.node:
            continue
        table_rows[b.id] = _cells(b.node[0])
        columns[b.id] = [_ALIGN.get(spec[0]["t"], "l") for spec in b.node[0]["c"][2]]
        for r in table_rows[b.id][0]:
            for n, (_, _, blocks) in enumerate(r):
                cell_pieces.append(_flatten_tables(blocks) or [{"t": "Plain", "c": []}])
                cell_keys.append((id(r), n))
    cell_latex = dict(zip(cell_keys, pandoc.blocks_to(cell_pieces, m.api, "latex")))

    # 2. assemble, with our own LaTeX for structured blocks
    out = []
    for b in m.blocks:
        if b.kind == "heading":
            text = next(short_latex)
            if _UNNUMBERED.match(_plain_heading(b.text)):
                out.append({"t": "RawBlock", "c": ["latex", f"\\section*{{{text}}}"]})
                continue
            command = ["section", "subsection", "subsubsection", "paragraph"][min(b.level, 4) - 1]
            out.append({"t": "RawBlock", "c": ["latex", f"\\{command}{{{text}}}"]})
        elif b.kind == "figure":
            out.append({"t": "RawBlock", "c": ["latex", _figure_latex(b, next(short_latex), project)]})
        elif b.kind == "table":
            caption = next(short_latex)
            if b.id in table_rows:
                rows, header_rows = table_rows[b.id]
                out.append({"t": "RawBlock", "c": ["latex", _table_latex(
                    b, caption, rows, header_rows, cell_latex, columns.get(b.id, []))]})
        elif b.kind == "equation":
            maths = b.text.strip()
            if not re.match(r"\\begin\{(equation|align|gather|multline|eqnarray|flalign)\*?\}", maths):
                maths = f"\\begin{{equation}}\n{maths}\n\\end{{equation}}"
            out.append({"t": "RawBlock", "c": ["latex", maths]})
        elif b.kind == "references":
            entries = [next(short_latex) for _ in b.entries]
            out.append({"t": "RawBlock", "c": ["latex", _references_latex(m, b, entries)]})
        elif b.id in parsed:
            out += _bounded(parsed[b.id])
        else:
            out += _bounded(b.node)

    return _unwrap_environments(pandoc.blocks_to([out], m.api, "latex")[0])


_WRAPPED = re.compile(r"\\\[\s*((?:\\label\{[^}]*\}\s*)?)"
                      r"(\\begin\{(align|gather|multline|eqnarray|flalign|equation)(\*?)\})"
                      r"(.*?)(\\end\{\3\4\})\s*\\\]", re.S)


def _unwrap_environments(latex: str) -> str:
    """pandoc puts an align written inside a paragraph in \\[ ... \\]; LaTeX refuses the nesting.

    A \\label written before the align moves inside it, onto the first of
    its lines that has no label of its own (amsmath allows one per line).
    """
    def place(m: re.Match) -> str:
        label, body = m.group(1).strip(), m.group(5)
        if label:
            lines = body.split("\\\\")
            free = next((n for n, line in enumerate(lines) if "\\label" not in line), None)
            if free is not None:
                lines[free] = lines[free].rstrip() + label + ("\n" if lines[free].endswith("\n") else "")
                body = "\\\\".join(lines)
        return m.group(2) + body + m.group(6)
    return _WRAPPED.sub(place, latex)


def _lines(affiliation: str, width: int = 45) -> str:
    """Break a long affiliation at its commas into lines, as IEEE author blocks do."""
    if len(affiliation) <= width:
        return affiliation
    lines, current = [], ""
    for part in [p.strip() for p in affiliation.split(",") if p.strip()]:
        if current and len(current) + len(part) + 2 > width:
            lines.append(current)
            current = part
        else:
            current = f"{current}, {part}" if current else part
    lines.append(current)
    return " \\\\\n".join(lines)


def render(m: Manuscript, project: Path, template: str = "ieee") -> str:
    """The complete .tex for the paper."""
    front = pandoc.markdown_to_latex(
        [m.title, m.abstract, m.keywords] + [x for a in m.authors for x in (a.name, a.affiliation)])
    title, abstract, keywords, people = front[0], front[1], front[2], front[3:]
    authors = [{"name": people[i], "affiliation": _lines(people[i + 1])}
               for i in range(0, len(people), 2)]
    doc = {"title": title, "abstract": abstract, "keywords": keywords, "authors": authors,
           "body": body_latex(m, project), "bibliography": "", "preamble": m.preamble}
    return _env().get_template(f"{template}.tex.j2").render(doc=doc)

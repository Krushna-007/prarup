"""What is missing from the paper, found from its structure.

Pure: reads the Manuscript (and checks image files exist), runs nothing.
Every finding names the block it is about, so the window can jump to it.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from prarup.manuscript import Manuscript

PLACEABLE = {".png", ".jpg", ".jpeg", ".pdf"}
CONVERTIBLE = {".gif", ".bmp", ".tif", ".tiff", ".webp"}


@dataclass
class Finding:
    code: str
    severity: str          # "error" or "warning"
    message: str
    block_id: str = ""     # "" for the front matter
    group: str = "Missing"  # which panel lists it: Missing, Images, Structure


def _cited_keys(m: Manuscript) -> set:
    """Citation keys used anywhere in the text: [@key] and \\cite{a,b}."""
    keys = set()
    for b in m.blocks:
        if b.kind in ("references", "figure"):
            continue
        for found in re.findall(r"@([\w:.\-/]+)", b.text):
            keys.add(found.rstrip(".,;"))
        for group in re.findall(r"\\cite[pt]?\*?\{([^}]*)\}", b.text):
            keys.update(k.strip() for k in group.split(","))
    return keys


def _numeric_citations(m: Manuscript) -> set:
    """Reference numbers cited as [3], [2, 5] or [4-6] in running text and the abstract."""
    numbers = set()
    texts = [m.abstract] + [b.text for b in m.blocks if b.kind in ("para", "list", "quote")]
    for text in texts:
        for group in re.findall(r"\\?\[(\d+(?:\s*[-–,]\s*\d+)*)\\?\]", text):
            for part in re.split(r"\s*,\s*", group):
                if re.match(r"\d+\s*[-–]\s*\d+", part):
                    a, z = map(int, re.split(r"\s*[-–]\s*", part))
                    numbers.update(range(a, z + 1))
                else:
                    numbers.add(int(part))
    return numbers


def _roman(text: str) -> int:
    """IEEE numbers tables in Roman numerals: "Table IV" is table 4."""
    values = {"I": 1, "V": 5, "X": 10}
    total, previous = 0, 0
    for char in reversed(text.upper()):
        value = values[char]
        total += -value if value < previous else value
        previous = max(previous, value)
    return total


def _mentions(m: Manuscript, kind: str) -> tuple[set, set]:
    """(labels referenced, numbers mentioned as "Fig. 3"/"Table 2") in running text."""
    labels, numbers = set(), set()
    word = r"(?:fig(?:ure)?s?\.?)" if kind == "figure" else r"(?:tables?)"
    for b in m.blocks:
        if b.kind in ("figure", "table", "references"):
            continue
        labels.update(re.findall(r"\(#([^)\s]+)\)", b.text))
        labels.update(re.findall(r"\\(?:ref|autoref|cref)\{([^}]+)\}", b.text))
        for n in re.findall(word + r"\s*~?\s*(\d+|[IVX]+)\b", b.text, re.I):
            numbers.add(int(n) if n.isdigit() else _roman(n))
    return labels, numbers


def analyze(m: Manuscript, project: Path) -> list[Finding]:
    found: list[Finding] = []
    add = lambda *a, **k: found.append(Finding(*a, **k))

    # front matter
    if not m.title.strip():
        add("META-01", "error", "The paper has no title.")
    if not m.authors:
        add("META-02", "error", "No authors were found.")
    else:
        for a in m.authors:
            if not a.affiliation.strip():
                add("META-02", "warning", f"{a.name} has no affiliation.")
    if not m.abstract.strip():
        add("META-03", "error", "The paper has no abstract.")
    if not m.keywords.strip():
        add("META-04", "warning", "No keywords (IEEE calls them Index Terms).")

    # figures and tables
    labels, figure_numbers = _mentions(m, "figure")
    _, table_numbers = _mentions(m, "table")
    for n, fig in enumerate(m.figures(), start=1):
        name = f"Fig. {n}"
        if not fig.caption.strip():
            add("FIG-01", "warning", f"{name} has no caption.", fig.id)
        if not fig.images:
            add("FIG-03", "error", f"{name} has a caption but no image.", fig.id)
        for path in fig.images:
            file = project / path
            if not file.is_file():
                add("FIG-03", "error", f"{name}: image '{Path(path).name}' is missing.", fig.id)
            elif file.suffix.lower() not in PLACEABLE | CONVERTIBLE:
                add("FIG-04", "error", f"{name}: {file.suffix} images cannot be placed in the PDF; "
                    f"replace it with a PNG or PDF.", fig.id)
        cited = (fig.label and fig.label in labels) or (n in figure_numbers) or (
            fig.number and fig.number in figure_numbers)
        if not cited:
            add("FIG-02", "warning", f"{name} is never mentioned in the text.", fig.id)

    for n, tab in enumerate(m.tables(), start=1):
        name = f"Table {n}"
        if not tab.caption.strip():
            add("TAB-01", "warning", f"{name} has no caption.", tab.id)
        if not ((tab.label and tab.label in labels) or n in table_numbers):
            add("TAB-02", "warning", f"{name} is never mentioned in the text.", tab.id)

    # references
    refs = [b for b in m.blocks if b.kind == "references"]
    entries = sum(len(r.entries) for r in refs)
    if not refs or not entries:
        add("REF-01", "error", "The paper has no references.")
    keys = {k for r in refs for k in r.keys}
    if keys:
        cited = _cited_keys(m)
        for key in sorted(cited - keys):
            add("REF-02", "error", f"Citation [{key}] has no matching reference.",
                next((b.id for b in m.blocks if key in b.text), ""))
        for r in refs:
            for key in r.keys:
                if key not in cited:
                    add("REF-03", "warning", f"Reference [{key}] is never cited.", r.id)
    elif entries:
        numbers = _numeric_citations(m)
        # a [99] in a paper with 50 references is broken whatever the citation style
        for n in sorted(x for x in numbers if x > entries):
            add("REF-02", "error", f"Citation [{n}] points past the {entries} references.",
                next((b.id for b in m.blocks if b.kind in ("para", "list", "quote")
                      and re.search(rf"\\?\[{n}\\?\]", b.text)), ""))
        if len(numbers) >= 3:                 # the paper uses numbered citations
            for n in range(1, entries + 1):
                if n not in numbers:
                    add("REF-03", "warning", f"Reference [{n}] is never cited.", refs[0].id)

    # structure
    headings = [b.text.lower() for b in m.blocks if b.kind == "heading"]
    if not any("introduction" in h for h in headings):
        add("STR-01", "warning", "No Introduction section.", group="Structure")
    if not any(re.search(r"conclu", h) for h in headings):
        add("STR-01", "warning", "No Conclusion section.", group="Structure")
    for i, b in enumerate(m.blocks):
        nxt = m.blocks[i + 1] if i + 1 < len(m.blocks) else None
        # headings guessed from bold text all get level 1, so a sub-heading
        # under them would look like an empty section: only trust real levels
        if b.kind == "heading" and not b.detected and (
                nxt is None or nxt.kind == "heading" and nxt.level <= b.level):
            add("STR-02", "warning", f"Section '{b.text[:40]}' is empty.", b.id, group="Structure")
    return found

import re
from pathlib import Path

_INPUT = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
_COMMENT = re.compile(r"(?<!\\)%[^\n]*")


def full_source(main: Path, seen: set | None = None) -> str:
    seen = seen if seen is not None else set()
    main = main.resolve()
    if main in seen or not main.is_file():
        return ""
    seen.add(main)
    text = _COMMENT.sub("", main.read_text(encoding="utf-8", errors="replace"))

    def inline(match: re.Match) -> str:
        name = match.group(1).strip()
        for candidate in (main.parent / name, main.parent / f"{name}.tex"):
            if candidate.is_file():
                return full_source(candidate, seen)
        return ""

    return _INPUT.sub(inline, text)


def _group(text: str, start: int) -> tuple[str, int]:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    return text[start + 1:], len(text)


def _command_args(text: str, command: str) -> list[str]:
    found = []
    for m in re.finditer(r"\\" + command + r"\s*(?=\{)", text):
        arg, _ = _group(text, m.end())
        found.append(arg)
    return found


def ieee_author_blocks(source: str) -> list[tuple[str, str]]:
    authors = _command_args(source, "author")
    if not authors:
        return []
    names = _command_args(authors[0], "IEEEauthorblockN")
    places = _command_args(authors[0], "IEEEauthorblockA")
    if not names:
        return [(authors[0], "")]
    return [(n, places[i] if i < len(places) else "") for i, n in enumerate(names)]


def bibitems(source: str) -> list[tuple[str, str]]:
    body = re.search(r"\\begin\{thebibliography\}(?:\{[^}]*\})?(.*?)\\end\{thebibliography\}",
                     source, re.S)
    if not body:
        return []
    items = re.split(r"\\bibitem\s*(?:\[[^\]]*\])?\s*", body.group(1))[1:]
    entries = []
    for item in items:
        if item.startswith("{"):
            key, end = _group(item, 0)
            entries.append((key.strip(), " ".join(item[end:].split())))
    return entries


def bib_keys(bib_text: str) -> list[str]:
    return re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib_text)


def bibliography_files(source: str) -> list[str]:
    names = []
    for arg in _command_args(source, "bibliography"):
        names += [n.strip() for n in arg.split(",") if n.strip()]
    return names


def bib_entries(bib_text: str) -> list[tuple[str, dict]]:
    entries = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", bib_text):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        body, _ = _group(bib_text, m.end() - len(m.group(0)) + m.group(0).index("{"))
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*", body):
            rest = body[f.end():]
            if rest.startswith("{"):
                value, _ = _group(rest, 0)
            elif rest.startswith('"'):
                value = rest[1:].split('"', 1)[0]
            else:
                value = re.split(r"[,\n]", rest, 1)[0]
            fields.setdefault(f.group(1).lower(), " ".join(value.split()))
        entries.append((m.group(2), fields))
    return entries


def describe_entry(fields: dict) -> str:
    venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher", "")
    parts = [fields.get("author", "").replace(" and ", ", "), f"``{fields.get('title', '')}''",
             f"\\emph{{{venue}}}" if venue else "", fields.get("year", "")]
    return ", ".join(p for p in parts if p and p != "``''") + "."


SAFE_PACKAGES = {
    "amsmath", "amssymb", "amsfonts", "amsthm", "bm", "mathrsfs", "mathtools", "dsfont",
    "bbm", "bbold", "nccmath", "siunitx", "xspace", "algorithm", "algorithmic",
    "algpseudocode", "algorithm2e", "multirow", "makecell", "physics", "esint",
    "upgreek", "cancel", "stmaryrd", "units", "nicefrac", "xfrac", "tikz", "pgfplots",
    "subcaption", "booktabs", "array", "soul", "ulem", "comment", "enumitem",
}
_DEFINITIONS = re.compile(r"\\(newcommand|renewcommand|providecommand|DeclareMathOperator|"
                          r"newtheorem|def|newenvironment)\b\*?")


def preamble_extras(source: str) -> str:
    preamble = source.split("\\begin{document}", 1)[0]
    lines = []
    for m in re.finditer(r"\\usepackage\s*(\[[^\]]*\])?\s*\{([^}]*)\}", preamble):
        wanted = [p.strip() for p in m.group(2).split(",") if p.strip() in SAFE_PACKAGES]
        if wanted:
            lines.append(f"\\usepackage{m.group(1) or ''}{{{','.join(wanted)}}}")
    for m in _DEFINITIONS.finditer(preamble):
        start, end = m.start(), m.end()

        i = end
        while i < len(preamble):
            while i < len(preamble) and preamble[i] in " \t":
                i += 1
            if i < len(preamble) and preamble[i] == "{":
                _, i = _group(preamble, i)
            elif i < len(preamble) and preamble[i] == "[":
                i = preamble.find("]", i) + 1 or len(preamble)
            elif m.group(1) == "def" and i < len(preamble) and preamble[i] == "\\":
                i = re.match(r"\\[A-Za-z@]+[^{]*", preamble[i:]).end() + i
            elif m.group(1) in ("newcommand", "renewcommand", "providecommand",
                                "DeclareMathOperator") and preamble[i] == "\\" and i == end + 0:
                i = re.match(r"\\[A-Za-z@]+", preamble[i:]).end() + i
            else:
                break
        text = preamble[start:i]
        if m.group(1) in ("newcommand", "renewcommand"):
            text = "\\providecommand" + text[len(m.group(0)):] if m.group(1) == "newcommand" else text
        lines.append(text)
    return "\n".join(lines)

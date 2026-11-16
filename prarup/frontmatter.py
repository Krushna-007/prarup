import re

from prarup.models import Author


_ORGANISATION = {
    "university", "institute", "dept", "dept.", "department", "school", "college",
    "laboratory", "lab", "centre", "center", "faculty", "inc", "inc.", "ltd", "ltd.",
}

_UNESCAPE = {r"\%": "%", r"\&": "&", r"\_": "_", r"\#": "#", r"\$": "$",
             r"\{": "{", r"\}": "}", r"\textbackslash{}": "\\",
             r"\^{}": "^", r"\textasciitilde{}": "~", r"\textasciicircum{}": "^"}


def latex_to_plain(latex: str) -> str:
    text = re.sub(r"\\label\{[^}]*\}", "", latex)
    text = re.sub(r"\\textsuperscript\{[^}]*\}", "", text)
    text = text.replace("\\\\", "\x00")
    text = text.replace("~", " ")
    for escaped, char in _UNESCAPE.items():
        text = text.replace(escaped, char)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", text)
    text = text.replace("---", "—").replace("--", "–")
    lines = [" ".join(part.split()) for part in text.split("\x00")]
    return "\n".join(line for line in lines if line)


_SUPERSCRIPTS = "¹²³⁴⁵⁶⁷⁸⁹⁰"
_MARKER = re.compile(r"[" + _SUPERSCRIPTS + r"*†‡§‖]+|(?<=[a-zà-ÿ])\d+$")
_LABEL = re.compile(r"(?i)^(authors?|author\(s\)|by)\s*:?$")
_NAME_WORD = r"(?:[A-Z][a-zà-ÿ'’]+(?:-[A-Z][a-zà-ÿ'’]+)*|[A-Z]\.(?:[A-Z]\.)*)"


def _looks_like_a_name(text: str) -> bool:
    words = text.split()
    if not 2 <= len(words) <= 4 or re.search(r"[\d@]", text):
        return False
    if any(w.lower().strip(",") in _ORGANISATION for w in words):
        return False

    return all(re.fullmatch(_NAME_WORD, w) for w in words)


def _split_marks(text: str) -> tuple[str, set]:
    marks = set()
    for m in _MARKER.finditer(text):
        for char in m.group():
            marks.add(str(_SUPERSCRIPTS.index(char) + 1 if char in _SUPERSCRIPTS[:9]
                          else 0 if char == "⁰" else char))
    return _clean_name(_MARKER.sub("", text)), marks


def _clean_name(text: str) -> str:
    text = re.sub(r"^\d+(st|nd|rd|th)\s+", "", text.strip())
    return text.strip(" ,*†‡§‖0123456789" + _SUPERSCRIPTS)


def read_authors(paragraphs: list[str]) -> list[Author]:
    authors, group, marks = [], [], {}

    def attach(text: str, to: list) -> None:
        for author in to:
            author.affiliation = ", ".join(p for p in (author.affiliation, text) if p)

    for paragraph in paragraphs:
        for number, line in enumerate(l.strip() for l in paragraph.split("\n")):
            if not line or _LABEL.match(line):
                continue
            marked = re.match(r"^([" + _SUPERSCRIPTS + r"*†‡§‖]+|\d+)\s*(\S.*)$", line)
            parts = [p for p in re.split(r",\s*|\s+and\s+|\s*&\s*", line) if p.strip()]
            names = [_split_marks(p) for p in parts]

            if marked and marks and marked.group(1) not in ("",):
                key = (str(_SUPERSCRIPTS.index(marked.group(1)[0]) + 1)
                       if marked.group(1)[0] in _SUPERSCRIPTS[:9] else marked.group(1))
                attach(marked.group(2), [a for a in authors if key in marks.get(id(a), set())])
            elif "@" in line or line.lower().startswith(("email", "e-mail")):
                attach(line, group or authors[-1:])
            elif len(names) > 1 and all(_looks_like_a_name(n) for n, _ in names):
                group = [Author(n) for n, _ in names]
                for author, (_, m) in zip(group, names):
                    marks[id(author)] = m
                authors += group
            elif _looks_like_a_name(names[0][0]) and (len(parts) == 1 or number == 0):
                author = Author(names[0][0], ", ".join(parts[1:]) if number == 0 else "")
                marks[id(author)] = names[0][1]
                group = [author]
                authors.append(author)
            elif not authors:
                group = [Author(_clean_name(line))]
                authors += group
            else:
                attach(line, group or authors[-1:])
    return authors


def title_and_authors(paragraphs: list[str]) -> tuple[str, list[Author]]:
    paragraphs = [p for p in paragraphs if p.strip()]
    if not paragraphs:
        return "", []
    title = " ".join(paragraphs[0].split()).strip("\"“”'")
    return title, read_authors(paragraphs[1:])

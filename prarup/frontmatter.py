"""Find the title, authors and abstract in a Word paper's LaTeX.

A Word file rarely marks these with styles pandoc understands. Usually
they are ordinary paragraphs above the first heading, so pandoc puts them
in the body, where they would print as plain text. This file recognises
them and takes them out.

The anchor is the abstract. A paragraph starting "Abstract" is
unmistakable; everything above it is the title and then the authors.
Without one, nothing is taken, because a first paragraph could just as
well be the paper's opening text.

Pure string work: no files, no processes.
"""

import re

from prarup.models import Author

_ABSTRACT = re.compile(r"(?is)^abstract\b[\s—–:.\-]*(?P<rest>.*)$")
_KEYWORDS = re.compile(r"(?is)^(?:keywords|key words|index terms)\b[\s—–:.\-]*(?P<rest>.*)$")
_SECTION = re.compile(r"\\section\*?\{")

# Words that mark a line as an affiliation rather than a person's name
_ORGANISATION = {
    "university", "institute", "dept", "dept.", "department", "school", "college",
    "laboratory", "lab", "centre", "center", "faculty", "inc", "inc.", "ltd", "ltd.",
}

_UNESCAPE = {r"\%": "%", r"\&": "&", r"\_": "_", r"\#": "#", r"\$": "$",
             r"\{": "{", r"\}": "}", r"\textbackslash{}": "\\",
             r"\^{}": "^", r"\textasciitilde{}": "~", r"\textasciicircum{}": "^"}


def latex_to_plain(latex: str) -> str:
    """Readable text from pandoc's LaTeX: formatting dropped, line breaks kept."""
    text = re.sub(r"\\label\{[^}]*\}", "", latex)
    text = re.sub(r"\\textsuperscript\{[^}]*\}", "", text)   # affiliation markers
    text = text.replace("\\\\", "\x00")                    # Shift+Enter line break
    text = text.replace("~", " ")                           # LaTeX's non-breaking space
    for escaped, char in _UNESCAPE.items():
        text = text.replace(escaped, char)
    previous = None
    while previous != text:                                 # innermost first
        previous = text
        text = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", text)
    text = text.replace("---", "—").replace("--", "–")
    lines = [" ".join(part.split()) for part in text.split("\x00")]
    return "\n".join(line for line in lines if line)


def escape_latex(text: str) -> str:
    """Plain text made safe to put in LaTeX. A bare % would start a comment."""
    text = text.replace("\\", "\x00")
    for char in "&%$#_{}":
        text = text.replace(char, "\\" + char)
    text = text.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")
    return text.replace("\x00", r"\textbackslash{}")


def _looks_like_a_name(text: str) -> bool:
    words = text.split()
    if not 2 <= len(words) <= 4 or re.search(r"[\d@]", text):
        return False
    if any(w.lower().strip(",") in _ORGANISATION for w in words):
        return False
    # "Asha", "Rao", "A." pass; "IIT" and "DA-IICT" do not
    return all(re.fullmatch(r"[A-Z][a-z'’\-]+|[A-Z]\.", w) for w in words)


def _clean_name(text: str) -> str:
    text = re.sub(r"^\d+(st|nd|rd|th)\s+", "", text.strip())   # "1st Given Name"
    return text.strip(" ,*†‡0123456789")


def read_authors(paragraphs: list[str]) -> list[Author]:
    """Read one or more authors from each paragraph between title and abstract."""
    authors = []
    for paragraph in paragraphs:
        lines = paragraph.split("\n")
        if len(lines) > 1:
            authors.append(Author(_clean_name(lines[0]), ", ".join(lines[1:])))
            continue
        line = lines[0]
        names = [_clean_name(n) for n in re.split(r",\s*|\s+and\s+", line) if n.strip()]
        if len(names) > 1 and all(_looks_like_a_name(n) for n in names):
            authors += [Author(n) for n in names]
        elif "," in line:
            name, affiliation = line.split(",", 1)
            authors.append(Author(_clean_name(name), affiliation.strip()))
        elif _looks_like_a_name(_clean_name(line)) or not authors:
            authors.append(Author(_clean_name(line)))
        else:                       # a stray affiliation line belongs to the last author
            last = authors[-1]
            last.affiliation = ", ".join(p for p in (last.affiliation, line) if p)
    return authors


def split_front_matter(fragment: str) -> tuple[dict, str]:
    """({title, authors, abstract, keywords}, body without them).

    Returns ({}, fragment) unchanged when no abstract is found.
    """
    section = _SECTION.search(fragment)
    cut = section.start() if section else len(fragment)
    paragraphs = [p for p in re.split(r"\n\s*\n", fragment[:cut]) if p.strip()]
    plain = [latex_to_plain(p) for p in paragraphs]

    where = next((i for i, p in enumerate(plain) if _ABSTRACT.match(p)), None)
    if where is None:
        return {}, fragment

    abstract = _ABSTRACT.match(plain[where]).group("rest").strip()
    used = where + 1
    if not abstract and used < len(plain):          # "Abstract" alone, text below it
        abstract = plain[used].replace("\n", " ")
        used += 1

    keywords = ""
    if used < len(plain) and _KEYWORDS.match(plain[used]):
        keywords = _KEYWORDS.match(plain[used]).group("rest").replace("\n", " ").strip()
        used += 1

    found = {
        "title": plain[0].replace("\n", " ") if where > 0 else "",
        "authors": read_authors(plain[1:where]),
        "abstract": " ".join(abstract.split()),
        "keywords": keywords,
    }
    rest = "\n\n".join(paragraphs[used:])
    return found, (rest + "\n\n" if rest else "") + fragment[cut:]

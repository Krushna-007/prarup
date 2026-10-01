"""Build a Document from a LaTeX fragment.

Pure string work. No file access, no subprocess.
"""

import re

from prarup.models import Author, Document

# \section{Title} optionally followed by pandoc's \label{...}
_FIRST_SECTION = re.compile(
    r"\\section\*?\{(?P<title>[^}]*)\}(?:\s*\\label\{[^}]*\})?\s*",
    re.MULTILINE,
)

# Every top-level heading. \section{ does not match inside \subsection{
# or \subsubsection{, because the pattern is anchored on the backslash.
_ALL_SECTIONS = re.compile(r"\\section\*?\{")
_ANY_SUBSECTION = re.compile(r"\\subsection\*?\{")

# Shallowest first. Going the other way, \subsubsection becomes
# \subsection and is then promoted a second time by the next rule,
# landing at \section two levels up instead of one.
#
# This order is safe because the patterns are anchored on the backslash:
# \subsection{ does not match inside \subsubsection{, where "subsection"
# appears without a backslash in front of it.
_PROMOTIONS = [
    (re.compile(r"\\subsection(\*?)\{"), r"\\section\1{"),
    (re.compile(r"\\subsubsection(\*?)\{"), r"\\subsection\1{"),
]


def _promote_headings(body: str) -> str:
    """Move every heading up one level.

    Needed after the top-level heading has been taken as the title,
    which would otherwise leave the real sections one level too deep.
    """
    for pattern, replacement in _PROMOTIONS:
        body = pattern.sub(replacement, body)
    return body


# \begin{figure} with no placement and no star. LaTeX may then float it
# to the top of the column, which in IEEEtran puts it above the abstract.
_BARE_FIGURE = re.compile(r"\\begin\{figure\}(?!\*)(?!\[)")


def _place_floats(body: str) -> str:
    """Give pandoc's figures a placement specifier.

    Only bare \\begin{figure} is touched. An explicit placement is the
    author's choice, and figure* spans both columns under different rules.
    """
    return _BARE_FIGURE.sub(r"\\begin{figure}[htbp]", body)


def document_from_latex(
    fragment: str,
    title: str = "",
    authors: list[Author] | None = None,
    abstract: str = "",
) -> Document:
    """Turn a LaTeX body fragment into a Document.

    A word processor document usually carries its own name as the single
    top-level heading, with the real sections nested under it. That
    heading is structural, not content: left in place it renders as
    section I with Introduction as a subsection of it.

    Structure alone cannot always settle it. A fragment that is one
    \\section{...} followed by text might be a titled document or a single
    real section; the LaTeX is identical either way. So two signals are
    used together.

    A lone top-level heading with subsections under it is a wrapper, and
    is removed whatever the caller passed, because leaving it turns the
    paper's own name into section I with Introduction nested inside it.

    A lone top-level heading with nothing nested is only treated as a
    title when the caller gave none. Guessing then is better than an
    empty \\title{}, but once a real title is supplied the heading is
    far more likely to be a genuine section, so it stays.

    Several top-level headings are always real sections.
    """
    body = fragment
    only_heading = len(_ALL_SECTIONS.findall(body)) == 1
    has_subsections = _ANY_SUBSECTION.search(body) is not None

    if only_heading and (has_subsections or not title):
        match = _FIRST_SECTION.search(body)
        if match:
            if not title:
                title = match.group("title").strip()
            body = body[: match.start()] + body[match.end():]
            body = _promote_headings(body)

    body = _place_floats(body)

    return Document(
        title=title,
        authors=authors or [],
        abstract=abstract,
        body=body.strip(),
    )

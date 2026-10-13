"""Checks that run against a compiled PDF.

Everything in this file is a plain function: give it a path, get a list of
Issues back. Nothing here starts a process, opens a window or touches the
network, which is what makes it easy to test.
"""

from pathlib import Path

import pymupdf

from prarup.models import Issue, Rules


class UnreadablePdf(Exception):
    """Raised when the file is missing or is not a PDF at all."""


def _open(pdf_path: Path) -> pymupdf.Document:
    """Open a PDF, or raise UnreadablePdf with a sentence a user can read.

    filetype is forced so a .tex or .txt handed in by mistake is read as
    a broken PDF rather than quietly opened as plain text.
    """
    try:
        return pymupdf.open(pdf_path, filetype="pdf")
    except (pymupdf.FileDataError, pymupdf.FileNotFoundError) as exc:
        raise UnreadablePdf(f"{Path(pdf_path).name} is not a readable PDF") from exc


def plain_font_name(name: str) -> str:
    """Drop the subset tag, so FHXFSG+Times reads as Times.

    The six-letter tag only marks which glyphs were embedded. Two subsets
    of one font are the same problem for the author.
    """
    if not name:
        return "an unnamed font"
    tag, plus, rest = name.partition("+")
    if plus and len(tag) == 6 and tag.isupper():
        return rest
    return name


def describe_pages(pages) -> str:
    """Turn [2, 5, 7, 8, 9] into "pages 2, 5, 7-9"."""
    pages = sorted(set(pages))
    if len(pages) == 1:
        return f"page {pages[0]}"

    runs = []
    start = end = pages[0]
    for page in pages[1:]:
        if page == end + 1:
            end = page
            continue
        runs.append(f"{start}-{end}" if end > start else str(start))
        start = end = page
    runs.append(f"{start}-{end}" if end > start else str(start))
    return "pages " + ", ".join(runs)


def check_fonts(pdf_path: Path) -> list[Issue]:
    """Find fonts that a conference submission system will reject.

    Two different problems, which need two different answers:

    FONT-01  the font is referenced but not embedded. Ghostscript can
             embed it in place.
    FONT-02  the font is Type3, a bitmap format that IEEE rejects even
             when embedded. Nothing can repair this after the fact; the
             figure has to be exported again.

    Order matters. A Type3 font also reports no external file, so it must
    be matched first or it would be reported twice.

    A font used on many pages is one problem, so each font is reported
    once with the pages it appears on.
    """
    found = {}   # (code, name) -> pages, in the order first seen
    doc = _open(pdf_path)

    for number, page in enumerate(doc, start=1):
        for font in page.get_fonts(full=True):
            external_file = font[1]   # "n/a" when there is no font file
            font_type = font[2]       # "Type1", "TrueType", "Type0", "Type3"
            name = plain_font_name(font[3])

            if font_type == "Type3":
                found.setdefault(("FONT-02", name), []).append(number)
            elif external_file == "n/a":
                found.setdefault(("FONT-01", name), []).append(number)

    doc.close()

    issues = []
    for (code, name), pages in found.items():
        where = describe_pages(pages)
        if code == "FONT-02":
            issues.append(Issue(
                code=code,
                message=(f"{name} is a Type3 bitmap font ({where}). "
                         "Re-export the figure with matplotlib "
                         "rcParams['pdf.fonttype'] = 42"),
                severity="error",
                can_fix=False,
            ))
        else:
            issues.append(Issue(
                code=code,
                message=f"{name} is not embedded ({where})",
                severity="error",
                can_fix=True,
            ))
    return issues


def check_page_count(pdf_path: Path, rules: Rules) -> list[Issue]:
    """Report a paper that runs past the conference page limit.

    Counted on the compiled document, not on word count. Resizing one
    figure can move the page boundary, and no word count notices that.
    """
    doc = _open(pdf_path)
    pages = doc.page_count
    doc.close()

    if pages <= rules.page_limit:
        return []

    over = pages - rules.page_limit
    plural = "s" if over > 1 else ""
    return [Issue(
        code="GEOM-01",
        message=f"{over} page{plural} over the {rules.page_limit}-page limit",
        severity="warning",
        can_fix=False,
    )]


def check_security(pdf_path: Path) -> list[Issue]:
    """Report encryption or permission flags.

    A submission PDF must carry no password and no permission
    restrictions, even ones that still allow the file to be opened.
    """
    doc = _open(pdf_path)
    # Not is_encrypted. That reports whether the document is still locked,
    # and it goes False as soon as the file opens with an empty password,
    # which is exactly the case we need to catch. The metadata entry says
    # whether encryption is present at all.
    encryption = doc.metadata.get("encryption")
    doc.close()

    if encryption is None:
        return []

    return [Issue(
        code="DOC-01",
        message=f"the document is encrypted ({encryption})",
        severity="error",
        can_fix=True,
    )]


def check_bookmarks(pdf_path: Path) -> list[Issue]:
    """Report a PDF outline (bookmarks), usually left by hyperref.

    A warning rather than an error: some IEEE pipelines reject them and
    others do not. Not marked fixable, because Ghostscript keeps them.
    """
    doc = _open(pdf_path)
    count = len(doc.get_toc())
    doc.close()

    if count == 0:
        return []

    plural = "s" if count > 1 else ""
    return [Issue(
        code="DOC-02",
        message=(f"the PDF has {count} bookmark{plural}. Load hyperref with "
                 "[bookmarks=false], or drop it"),
        severity="warning",
        can_fix=False,
    )]


def run_all_checks(pdf_path: Path, rules: Rules) -> list[Issue]:
    """Run every check and return the findings, errors first.

    Adding a new check means writing the function above and adding one
    line here. That is the whole extension mechanism.
    """
    issues = []
    issues += check_fonts(pdf_path)
    issues += check_page_count(pdf_path, rules)
    issues += check_security(pdf_path)
    issues += check_bookmarks(pdf_path)

    # errors before warnings, so the blocking items are read first
    issues.sort(key=lambda issue: issue.severity != "error")
    return issues

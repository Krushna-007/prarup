"""Checks that run against a compiled PDF.

Everything in this file is a plain function: give it a path, get a list of
Issues back. Nothing here starts a process, opens a window or touches the
network, which is what makes it easy to test.
"""

from pathlib import Path

import pymupdf

from prarup.models import Issue, Rules


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
    """
    issues = []
    doc = pymupdf.open(pdf_path)

    for page in doc:
        for font in page.get_fonts(full=True):
            external_file = font[1]   # "n/a" when there is no font file
            font_type = font[2]       # "Type1", "TrueType", "Type0", "Type3"
            name = font[3]

            if font_type == "Type3":
                issues.append(Issue(
                    code="FONT-02",
                    message=f"{name} is a Type3 bitmap font",
                    severity="error",
                    can_fix=False,
                ))
            elif external_file == "n/a":
                issues.append(Issue(
                    code="FONT-01",
                    message=f"{name} is not embedded",
                    severity="error",
                    can_fix=True,
                ))

    doc.close()
    return issues


def check_page_count(pdf_path: Path, rules: Rules) -> list[Issue]:
    """Report a paper that runs past the conference page limit.

    Counted on the compiled document, not on word count. Resizing one
    figure can move the page boundary, and no word count notices that.
    """
    doc = pymupdf.open(pdf_path)
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
    doc = pymupdf.open(pdf_path)
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


def run_all_checks(pdf_path: Path, rules: Rules) -> list[Issue]:
    """Run every check and return the findings, errors first.

    Adding a new check means writing the function above and adding one
    line here. That is the whole extension mechanism.
    """
    issues = []
    issues += check_fonts(pdf_path)
    issues += check_page_count(pdf_path, rules)
    issues += check_security(pdf_path)

    # errors before warnings, so the blocking items are read first
    issues.sort(key=lambda issue: issue.severity != "error")
    return issues

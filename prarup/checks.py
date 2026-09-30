"""Checks that run against a compiled PDF.

Everything in this file is a plain function: give it a path, get a list of
Issues back. Nothing here starts a process, opens a window or touches the
network, which is what makes it easy to test.
"""

from pathlib import Path

import pymupdf

from prarup.models import Issue


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

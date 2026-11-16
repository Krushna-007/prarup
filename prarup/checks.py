import re
from pathlib import Path

import pymupdf

from prarup.models import Geometry, Issue, Rules


class UnreadablePdf(Exception):
    pass


def _open(pdf_path: Path) -> pymupdf.Document:
    try:
        return pymupdf.open(pdf_path, filetype="pdf")
    except (pymupdf.FileDataError, pymupdf.FileNotFoundError) as exc:
        raise UnreadablePdf(f"{Path(pdf_path).name} is not a readable PDF") from exc


def plain_font_name(name: str) -> str:
    if not name:
        return "an unnamed font"
    tag, plus, rest = name.partition("+")
    if plus and len(tag) == 6 and tag.isupper():
        return rest
    return name


def describe_pages(pages) -> str:
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


def read_geometry(doc: pymupdf.Document) -> Geometry | None:
    info = doc.xref_get_key(-1, "Info")
    if info[0] != "xref":
        return None
    raw = doc.xref_get_key(int(info[1].split()[0]), "PrarupGeometry")[1]
    numbers = [float(n) for n in re.findall(r"[\d.]+(?=pt)", raw)]
    return Geometry(*numbers) if len(numbers) == 4 else None



class PdfChecks:
    def __init__(self, document: pymupdf.Document, rules: Rules):
        self.document = document
        self.rules = rules

    def run(self) -> list[Issue]:
        issues = []
        for check in (self.fonts, self.page_count, self.security, self.bookmarks, self.figure_overflow):
            issues.extend(check())
        return sorted(issues, key=lambda issue: issue.severity != "error")

    def fonts(self) -> list[Issue]:
        found = {}

        for number, page in enumerate(self.document, start=1):
            for font in page.get_fonts(full=True):
                external_file = font[1]
                font_type = font[2]
                name = plain_font_name(font[3])

                if font_type == "Type3":
                    found.setdefault(("FONT-02", name), []).append(number)
                elif external_file == "n/a":
                    found.setdefault(("FONT-01", name), []).append(number)

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

    def page_count(self) -> list[Issue]:
        pages = self.document.page_count

        if pages <= self.rules.page_limit:
            return []

        over = pages - self.rules.page_limit
        plural = "s" if over > 1 else ""
        return [Issue(
            code="GEOM-01",
            message=f"{over} page{plural} over the {self.rules.page_limit}-page limit",
            severity="warning",
            can_fix=False,
        )]

    def security(self) -> list[Issue]:
        encryption = (self.document.metadata or {}).get("encryption")

        if encryption is None:
            return []

        return [Issue(
            code="DOC-01",
            message=f"the document is encrypted ({encryption})",
            severity="error",
            can_fix=True,
        )]

    def bookmarks(self) -> list[Issue]:
        count = len(self.document.get_toc())

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

    def figure_overflow(self) -> list[Issue]:
        geometry = read_geometry(self.document)
        issues = []
        if geometry is not None:
            centre = geometry.left + geometry.text / 2
            for number, page in enumerate(self.document, start=1):
                for image in page.get_images():
                    for rect in page.get_image_rects(image[0]):
                        spans_both = (abs((rect.x0 + rect.x1) / 2 - centre) < 2
                                      and rect.width <= geometry.text + 2)
                        low, high = geometry.bounds(rect.x0, spans_both)
                        over = max(rect.x1 - high, low - rect.x0)
                        if over > 2:
                            issues.append(Issue(
                                code="GEOM-02",
                                message=(f"a figure on page {number} runs {over:.0f} pt past "
                                         f"its column. Use Fit figures to resize it"),
                                severity="error",
                                can_fix=False,
                            ))
        return issues


def check_fonts(pdf_path: Path) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, Rules()).fonts()


def check_page_count(pdf_path: Path, rules: Rules) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, rules).page_count()


def check_security(pdf_path: Path) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, Rules()).security()


def check_bookmarks(pdf_path: Path) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, Rules()).bookmarks()


def check_figure_overflow(pdf_path: Path) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, Rules()).figure_overflow()


def run_all_checks(pdf_path: Path, rules: Rules) -> list[Issue]:
    with _open(pdf_path) as doc:
        return PdfChecks(doc, rules).run()

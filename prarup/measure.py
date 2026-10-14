"""Measure figures in a compiled PDF.

Reads what LaTeX reported (page geometry, the box of every graphic) from
a PDF built from figures.instrument(), and the printed size of the text
inside each figure. Vector figures are measured from their own text;
bitmaps are read with Tesseract OCR, so this file runs a process and
stays out of checks.py.
"""

import csv
import io
import re
import shutil
import statistics
import subprocess
from pathlib import Path

import pymupdf

from prarup.checks import read_geometry
from prarup.models import Graphic, Measured

BITMAP = {".png", ".jpg", ".jpeg"}
EXTENSIONS = ["", ".pdf", ".png", ".jpg", ".jpeg"]

# Tesseract's word box, as a fraction of the font size. Measured against
# matplotlib text of known size from 6 to 14 pt at 100 to 300 dpi: words
# with both a tall letter and a tail fill 0.96 of it, everything else 0.76.
TALL = set("bdfhklt0123456789")
TAIL = set("gjpqy")

# A point or two of rounding in LaTeX's own numbers is not an overflow;
# right-column figures land about 1.2 pt left of where the gap predicts.
TOLERANCE = 2.0


def graphic_boxes(doc: pymupdf.Document) -> dict:
    """{index: (page number, rect)} from the prarup:fig:N links."""
    boxes = {}
    for number, page in enumerate(doc, start=1):
        for link in page.get_links():
            found = re.fullmatch(r"prarup:fig:(\d+)", link.get("uri") or "")
            if found:
                boxes[int(found.group(1))] = (number, link["from"])
    return boxes


def small_text(sizes: list[float]) -> float | None:
    """The typical size of the smaller text: median of the lower half.

    Not the minimum, because a single superscript or a stray glyph would
    then decide the verdict for a whole figure.
    """
    if not sizes:
        return None
    sizes = sorted(sizes)
    return statistics.median(sizes[: max(1, len(sizes) // 2)])


def vector_text(page: pymupdf.Page, rect: pymupdf.Rect) -> float | None:
    """Printed size of the small text whose centre lies inside rect."""
    sizes = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                box = pymupdf.Rect(span["bbox"])
                centre = pymupdf.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
                if span["text"].strip() and centre in rect:
                    sizes.append(span["size"])
    return small_text(sizes)


def ocr_text_per_width(image: Path) -> float | None:
    """Font size per pixel of image width, read with Tesseract.

    Multiply by the printed width in points to get the printed font size,
    whatever the image's dpi. None without Tesseract or without words.
    """
    if shutil.which("tesseract") is None:
        return None
    result = subprocess.run(["tesseract", str(image), "-", "--psm", "11", "tsv"],
                            capture_output=True, text=True)
    sizes = []
    for row in csv.DictReader(io.StringIO(result.stdout), delimiter="\t"):
        word = (row.get("text") or "").strip()
        if row.get("level") != "5" or len(word) < 2 or float(row["conf"]) < 80:
            continue
        if not word.replace(".", "").isalnum():
            continue
        tall = any(c in TALL or c.isupper() for c in word)
        tail = any(c in TAIL for c in word)
        sizes.append(int(row["height"]) / (0.96 if tall and tail else 0.76))

    width = pymupdf.Pixmap(str(image)).width
    size = small_text(sizes) if len(sizes) >= 3 else None
    return None if size is None else size / width


def find_file(path: str, tex_dir: Path) -> Path | None:
    """Resolve an \\includegraphics path the way graphicx does."""
    for ext in EXTENSIONS:
        candidate = tex_dir / (path + ext)
        if candidate.is_file():
            return candidate
    return None


def measure(pdf_path: Path, graphics: list[Graphic], tex_dir: Path):
    """(geometry, [Measured]) for every graphic that reached the page."""
    doc = pymupdf.open(pdf_path)
    geometry = read_geometry(doc)
    boxes = graphic_boxes(doc)

    results = []
    for g in graphics:
        if g.index not in boxes:
            continue
        number, rect = boxes[g.index]
        m = Measured(g.index, number, rect.x0, rect.y0, rect.x1, rect.y1)

        if geometry:
            low, high = geometry.bounds(rect.x0, g.env == "figure*")
            m.overflow = max(0.0, rect.x1 - high - TOLERANCE, low - rect.x0 - TOLERANCE)

        source = find_file(g.path, tex_dir)
        if source and source.suffix.lower() in BITMAP:
            # font pixels per image pixel is already the ratio we want:
            # the image is scaled as a whole onto the page
            per_width = ocr_text_per_width(source)
            if per_width is not None:
                m.text_per_width, m.text_source = per_width, "ocr"
        else:
            size = vector_text(doc[number - 1], rect)
            if size is not None:
                m.text_per_width, m.text_source = size / rect.width, "vector"
        results.append(m)

    doc.close()
    return geometry, results

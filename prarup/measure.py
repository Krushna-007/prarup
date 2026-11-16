import csv
import io
import re
import statistics
from pathlib import Path

import pymupdf

from prarup.checks import read_geometry
from prarup.models import Graphic, Measured
from prarup.process import find_tool, run_tool

BITMAP = {".png", ".jpg", ".jpeg"}
EXTENSIONS = ["", ".pdf", ".png", ".jpg", ".jpeg"]


TALL = set("bdfhklt0123456789")
TAIL = set("gjpqy")


TOLERANCE = 2.0


def graphic_boxes(doc: pymupdf.Document) -> dict:
    boxes = {}
    for number, page in enumerate(doc, start=1):
        for link in page.get_links():
            found = re.fullmatch(r"prarup:fig:(\d+)", link.get("uri") or "")
            if found:
                boxes[int(found.group(1))] = (number, link["from"])
    return boxes


def small_text(sizes: list[float]) -> float | None:
    if not sizes:
        return None
    sizes = sorted(sizes)
    return statistics.median(sizes[: max(1, len(sizes) // 2)])


def vector_text(page: pymupdf.Page, rect: pymupdf.Rect) -> float | None:
    sizes = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                box = pymupdf.Rect(span["bbox"])
                centre = pymupdf.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)
                if span["text"].strip() and centre in rect:
                    sizes.append(span["size"])
    return small_text(sizes)


_OCR_CACHE: dict = {}


def ocr_text_per_width(image: Path) -> float | None:
    key = (str(image), image.stat().st_mtime if image.exists() else 0)
    if key not in _OCR_CACHE:
        _OCR_CACHE[key] = _ocr_text_per_width(image)
    return _OCR_CACHE[key]


def _ocr_text_per_width(image: Path) -> float | None:
    tesseract = find_tool("tesseract")
    if not tesseract:
        return None
    result = run_tool([tesseract, str(image), "-", "--psm", "11", "tsv"], errors="replace")
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
    for ext in EXTENSIONS:
        candidate = tex_dir / (path + ext)
        if candidate.is_file():
            return candidate
    return None


def measure(pdf_path: Path, graphics: list[Graphic], tex_dir: Path):
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

"""Tests for automatic repair.

The rule these enforce: a repair is only reported as successful if
re-running the check on the output confirms it. Ghostscript exits zero on
a file it did not change, so an exit code proves nothing.
"""

import shutil
from pathlib import Path

import pytest

from prarup.checks import check_fonts
from prarup.fix import GhostscriptNotFound, embed_fonts

FIXTURES = Path(__file__).parent / "fixtures"

needs_gs = pytest.mark.skipif(
    shutil.which("gs") is None, reason="ghostscript not installed"
)


@needs_gs
def test_embedding_removes_the_font_issue(tmp_path):
    """The repair must actually repair, verified by re-checking."""
    source = FIXTURES / "unembedded.pdf"
    assert check_fonts(source) != []          # broken to begin with

    repaired = embed_fonts(source, tmp_path / "fixed.pdf")

    assert repaired.exists()
    assert check_fonts(repaired) == []        # and clean afterwards


@needs_gs
def test_ghostscript_cannot_repair_type3(tmp_path):
    """Documented Ghostscript limitation, asserted rather than assumed.

    If this ever starts passing, the auto-fix branch in checks.py can be
    simplified. Until then FONT-02 must stay marked unfixable.
    """
    repaired = embed_fonts(FIXTURES / "mpl_type3.pdf", tmp_path / "out.pdf")
    codes = [i.code for i in check_fonts(repaired)]
    assert "FONT-02" in codes, "Ghostscript unexpectedly fixed a Type3 font"


def _paper_with_a_sharp_image(path):
    """Unembedded Helvetica plus a 1200x1200 lossless image in a 2-inch box.

    That is 600 dpi, above the 300 dpi /prepress downsamples to, and
    lossless, which /prepress would re-encode as JPEG.
    """
    import pymupdf

    size = 1200
    pixels = bytes((x * 7 + y * 13) % 256 for y in range(size) for x in range(size))
    image = pymupdf.Pixmap(pymupdf.csGRAY, size, size, pixels, False)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "caption", fontname="helv")
    page.insert_image(pymupdf.Rect(72, 100, 216, 244), pixmap=image)
    doc.save(path)
    doc.close()
    return path


@needs_gs
def test_embedding_fonts_leaves_images_untouched(tmp_path):
    """Fixing a font must not quietly lower figure quality.

    Rendered pixels are compared, not file bytes, because Ghostscript
    rewrites every object even when nothing changes.
    """
    import pymupdf

    source = _paper_with_a_sharp_image(tmp_path / "paper.pdf")
    repaired = embed_fonts(source, tmp_path / "fixed.pdf")

    before, after = pymupdf.open(source), pymupdf.open(repaired)
    image_before = before[0].get_images(full=True)[0]
    image_after = after[0].get_images(full=True)[0]
    assert image_after[2:4] == image_before[2:4]          # width, height
    assert image_after[8] != "DCTDecode"                  # not turned into JPEG

    box = before[0].get_image_rects(image_before[0])[0]
    assert (before[0].get_pixmap(dpi=300, clip=box).samples
            == after[0].get_pixmap(dpi=300, clip=box).samples)

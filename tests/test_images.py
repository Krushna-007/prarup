from pathlib import Path

import pytest
from PIL import Image

from prarup.images import dhash, findings, inspect
from prarup.manuscript import Block, Manuscript

PLOT = Path(__file__).parent / "fixtures" / "latex_project" / "figs" / "accuracy.png"


def test_duplicate_survives_resizing_and_recompression(tmp_path):
    with Image.open(PLOT) as im:
        im.convert("RGB").resize((im.width // 2, im.height // 2)).save(tmp_path / "copy.jpg", quality=70)
        original = dhash(im)
    with Image.open(tmp_path / "copy.jpg") as copy:
        assert bin(original ^ dhash(copy)).count("1") <= 4


def _paper(tmp_path, images: list[list[str]]) -> Manuscript:
    (tmp_path / "media").mkdir(exist_ok=True)
    blocks = [Block(id=f"b{n}", kind="figure", images=paths) for n, paths in enumerate(images)]
    return Manuscript(source="x.docx", blocks=blocks)


def test_effective_dpi_is_pixels_over_printed_inches(tmp_path):
    m = _paper(tmp_path, [["media/small.png"]])
    Image.new("RGB", (600, 400), "white").save(tmp_path / "media" / "small.png")
    [r] = inspect(m, tmp_path)
    assert r.dpi == pytest.approx(600 / (3.5 * 0.98), rel=0.01)
    [f] = findings([r])
    assert f.code == "IMG-01" and "175 dpi" in f.message


def test_duplicate_plot_is_reported(tmp_path):
    m = _paper(tmp_path, [["media/plot.png"], ["media/plot_again.png"]])
    for name in ("plot.png", "plot_again.png"):
        (tmp_path / "media" / name).write_bytes(PLOT.read_bytes())
    matches = [item for item in findings(inspect(m, tmp_path)) if item.code == "IMG-05"]
    assert len(matches) == 1
    assert "plot.png" in matches[0].message

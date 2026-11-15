"""Image forensics on real AI-generated images (fixtures/images/ATTRIBUTION.md)."""

from pathlib import Path

import pytest
from PIL import Image

from prarup.images import dhash, findings, inspect, inspect_file
from prarup.manuscript import Block, Manuscript

IMAGES = Path(__file__).parent / "fixtures" / "images"
PLOT = Path(__file__).parent / "fixtures" / "latex_project" / "figs" / "accuracy.png"


def test_google_c2pa_manifest_is_declared_ai():
    report, _ = inspect_file(IMAGES / "gemini_c2pa.jpg")
    assert report.verdict == "declared AI-generated"
    text = " ".join(e.text for e in report.evidence)
    assert "Created by Google Generative AI" in text
    assert "trainedAlgorithmicMedia" in text
    assert "signature valid" in text


def test_stable_diffusion_settings_are_generator_traces():
    report, _ = inspect_file(IMAGES / "sd_parameters.png")
    assert report.verdict == "AI generator traces"
    assert "Steps: 30, Sampler: Euler a" in report.evidence[0].text


@pytest.mark.parametrize("name", ["ai_stripped_elf.png", "ai_stripped_android.png"])
def test_stripped_ai_images_show_no_metadata_evidence(name):
    """Honest about the limit: metadata layers cannot see a stripped image."""
    report, _ = inspect_file(IMAGES / name)
    assert report.evidence == []


def test_an_ordinary_plot_shows_no_evidence():
    report, _ = inspect_file(PLOT)
    assert report.verdict == "no AI evidence found"


def test_duplicate_survives_resizing_and_recompression(tmp_path):
    with Image.open(PLOT) as im:
        im.convert("RGB").resize((im.width // 2, im.height // 2)).save(tmp_path / "copy.jpg", quality=70)
        original = dhash(im)
    with Image.open(tmp_path / "copy.jpg") as copy:
        assert bin(original ^ dhash(copy)).count("1") <= 4
    with Image.open(IMAGES / "ai_stripped_elf.png") as other:
        assert bin(original ^ dhash(other)).count("1") > 10


def _paper(tmp_path, images: list[list[str]]) -> Manuscript:
    (tmp_path / "media").mkdir(exist_ok=True)
    blocks = [Block(id=f"b{n}", kind="figure", images=paths) for n, paths in enumerate(images)]
    return Manuscript(source="x.docx", blocks=blocks)


def test_effective_dpi_is_pixels_over_printed_inches(tmp_path):
    """A 600 px image across one IEEE column (3.43 in) prints at 175 dpi."""
    m = _paper(tmp_path, [["media/small.png"]])
    Image.new("RGB", (600, 400), "white").save(tmp_path / "media" / "small.png")
    [r] = inspect(m, tmp_path)
    assert r.dpi == pytest.approx(600 / (3.5 * 0.98), rel=0.01)
    [f] = findings([r])
    assert f.code == "IMG-01" and "175 dpi" in f.message


def test_findings_for_ai_and_duplicates(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    for name in ("gemini_c2pa.jpg", "sd_parameters.png"):
        (media / name).write_bytes((IMAGES / name).read_bytes())
    (media / "plot.png").write_bytes(PLOT.read_bytes())
    (media / "plot_again.png").write_bytes(PLOT.read_bytes())
    m = _paper(tmp_path, [["media/gemini_c2pa.jpg"], ["media/sd_parameters.png"],
                          ["media/plot.png"], ["media/plot_again.png"]])
    codes = {f.code: f.message for f in findings(inspect(m, tmp_path))}
    assert "Created by Google Generative AI" in codes["IMG-02"]
    assert "Stable Diffusion" in codes["IMG-03"]
    assert "plot.png" in codes["IMG-05"]

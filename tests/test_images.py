"""Image checks on real images (see fixtures/images/ATTRIBUTION.md)."""

from pathlib import Path

import pytest
from PIL import Image

from prarup.images import (classifier_installed, dhash, findings, inspect, inspect_file,
                           photo_like)
from prarup.manuscript import Block, Manuscript

IMAGES = Path(__file__).parent / "fixtures" / "images"
PLOT = Path(__file__).parent / "fixtures" / "latex_project" / "figs" / "accuracy.png"


def _paper(tmp_path, images):
    (tmp_path / "media").mkdir(exist_ok=True)
    blocks = [Block(id=f"b{n}", kind="figure", images=paths) for n, paths in enumerate(images)]
    return Manuscript(source="x.docx", blocks=blocks)


def _copy(tmp_path, source, name):
    (tmp_path / "media").mkdir(exist_ok=True)
    (tmp_path / "media" / name).write_bytes(source.read_bytes())
    return f"media/{name}"


def test_google_c2pa_manifest_is_declared_ai():
    report, _ = inspect_file(IMAGES / "gemini_c2pa.jpg")
    assert report.verdict() == "declared AI-generated"
    assert "Created by Google Generative AI" in report.declared
    assert "signature valid" in report.declared


def test_stable_diffusion_settings_are_generator_traces():
    report, _ = inspect_file(IMAGES / "sd_parameters.png")
    assert report.verdict() == "AI generator traces"
    assert "Steps: 30, Sampler: Euler a" in report.traces


@pytest.mark.parametrize("name", ["ai_stripped_elf.png", "ai_stripped_android.png"])
def test_stripped_ai_images_show_no_metadata_evidence(name):
    report, _ = inspect_file(IMAGES / name)
    assert report.declared == "" and report.traces == ""


def test_an_ordinary_plot_shows_no_evidence():
    report, _ = inspect_file(PLOT)
    assert report.verdict() == "no AI evidence found"


def test_duplicate_survives_resizing_and_recompression(tmp_path):
    with Image.open(PLOT) as im:
        im.convert("RGB").resize((im.width // 2, im.height // 2)).save(tmp_path / "copy.jpg", quality=70)
        original = dhash(im)
    with Image.open(tmp_path / "copy.jpg") as copy:
        assert bin(original ^ dhash(copy)).count("1") <= 4


def test_effective_dpi_is_pixels_over_printed_inches(tmp_path):
    m = _paper(tmp_path, [["media/small.png"]])
    Image.new("RGB", (600, 400), "white").save(tmp_path / "media" / "small.png")
    [r] = inspect(m, tmp_path)
    assert r.dpi == pytest.approx(600 / (3.5 * 0.98), rel=0.01)
    [f] = findings([r])
    assert f.code == "IMG-01" and "175 dpi" in f.message


def test_findings_for_ai_and_duplicates(tmp_path):
    paths = [_copy(tmp_path, IMAGES / "gemini_c2pa.jpg", "gemini.jpg"),
             _copy(tmp_path, IMAGES / "sd_parameters.png", "sd.png"),
             _copy(tmp_path, PLOT, "plot.png"), _copy(tmp_path, PLOT, "plot_again.png")]
    m = _paper(tmp_path, [[p] for p in paths])
    codes = {f.code: f.message for f in findings(inspect(m, tmp_path))}
    assert "Created by Google Generative AI" in codes["IMG-02"]
    assert "Stable Diffusion" in codes["IMG-03"]
    assert "plot.png" in codes["IMG-05"]


@pytest.mark.parametrize("name", ["ai_stripped_elf.png", "ai_stripped_android.png", "sd_parameters.png"])
def test_ai_art_counts_as_photo_like(name):
    with Image.open(IMAGES / name) as im:
        assert photo_like(im)


def test_a_chart_is_not_photo_like_so_the_classifier_skips_it():
    with Image.open(PLOT) as im:
        assert not photo_like(im)


@pytest.mark.skipif(not classifier_installed(), reason="pip install -r requirements-ai.txt")
def test_classifier_flags_stripped_ai_art_but_skips_charts(tmp_path):
    m = _paper(tmp_path, [[_copy(tmp_path, IMAGES / "ai_stripped_elf.png", "elf.png")],
                          [_copy(tmp_path, PLOT, "plot.png")]])
    elf, plot = inspect(m, tmp_path, classify=True)
    assert elf.ai_score > 0.9 and elf.verdict() == "classifier: likely AI"
    assert plot.ai_score is None and "chart or diagram" in plot.ai_note
    assert [f.code for f in findings([elf, plot]) if f.code != "IMG-01"] == ["IMG-04"]

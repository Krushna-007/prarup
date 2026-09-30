"""Tests for .docx ingestion."""

import shutil
from pathlib import Path

import pytest

from prarup.convert import PandocNotFound, docx_to_tex, find_custom_macros

FIXTURES = Path(__file__).parent / "fixtures"

needs_pandoc = pytest.mark.skipif(
    shutil.which("pandoc") is None, reason="pandoc not installed"
)


@needs_pandoc
def test_produces_a_tex_file(tmp_path):
    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    assert tex.exists()
    assert tex.suffix == ".tex"


@needs_pandoc
def test_keeps_the_body_text(tmp_path):
    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    assert "Introduction" in tex.read_text()


@needs_pandoc
def test_extracts_the_images_to_disk(tmp_path):
    """pandoc writes \\includegraphics either way, but without
    --extract-media the file it points at is never created and the
    document compiles with a missing figure."""
    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    images = list(tmp_path.rglob("*.png")) + list(tmp_path.rglob("*.jpg"))
    assert images, "no image files were written"


@needs_pandoc
def test_every_referenced_image_resolves(tmp_path):
    """The path inside \\includegraphics must exist relative to the .tex."""
    import re

    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    refs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex.read_text())
    assert refs, "expected at least one figure reference"
    for ref in refs:
        assert (tmp_path / ref).exists(), f"{ref} is referenced but missing"


def test_custom_macros_are_detected():
    source = r"\newcommand{\vect}[1]{\mathbf{#1}}" "\n" r"\renewcommand{\deg}{^\circ}"
    assert find_custom_macros(source) == ["vect", "deg"]


def test_plain_source_reports_no_macros():
    assert find_custom_macros(r"\section{Intro} some text") == []

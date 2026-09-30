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


@needs_pandoc
def test_output_is_a_standalone_document(tmp_path):
    """pandoc -t latex emits a fragment by default, with no
    \\documentclass and no document environment, so it cannot compile."""
    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    source = tex.read_text()
    assert r"\documentclass" in source
    assert r"\begin{document}" in source


@needs_pandoc
@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_converted_document_actually_compiles(tmp_path):
    """The real check: does the .tex we produce build?"""
    from prarup.compile import compile_pdf

    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    pdf, log = compile_pdf(tex, tmp_path)
    assert pdf.exists(), f"compilation failed:\n{log}"


@needs_pandoc
def test_pandoc_own_macros_are_not_reported(tmp_path):
    """pandoc's standalone preamble defines tightlist and friends. Those
    are not the author's macros and must not be warned about."""
    tex = docx_to_tex(FIXTURES / "sample.docx", tmp_path)
    assert find_custom_macros(tex.read_text()) == []

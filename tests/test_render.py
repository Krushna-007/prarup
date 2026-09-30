"""Tests for the IEEE template renderer."""

import shutil
from pathlib import Path

import pytest

from prarup.models import Author, Document
from prarup.render import render

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)


def test_title_reaches_the_output():
    tex = render(Document(title="A Study of Things", body="Hello."))
    assert r"\title{A Study of Things}" in tex


def test_document_class_is_ieee_conference():
    tex = render(Document(title="T", body="x"))
    assert r"\documentclass[conference]{IEEEtran}" in tex


def test_authors_become_ieee_author_blocks():
    doc = Document(
        title="T",
        body="x",
        authors=[Author("Krushna Parmar", "DA-IICT"),
                 Author("Om Patel", "DA-IICT")],
    )
    tex = render(doc)
    assert r"\IEEEauthorblockN{Krushna Parmar}" in tex
    assert r"\IEEEauthorblockN{Om Patel}" in tex


def test_abstract_is_omitted_when_empty():
    """An empty abstract environment renders as a stray heading."""
    assert r"\begin{abstract}" not in render(Document(title="T", body="x"))


def test_abstract_is_included_when_present():
    tex = render(Document(title="T", body="x", abstract="We show that."))
    assert r"\begin{abstract}" in tex
    assert "We show that." in tex


def test_latex_braces_survive_the_template():
    """Jinja2's default delimiters collide with LaTeX. If the custom
    delimiters were not configured, this body would be mangled."""
    body = r"\section{Results} $\frac{a}{b}$ and \{literal braces\}"
    tex = render(Document(title="T", body=body))
    assert body in tex


@needs_tectonic
def test_rendered_document_compiles(tmp_path):
    """The only test that really matters: does IEEEtran accept it?"""
    from prarup.compile import compile_pdf

    doc = Document(
        title="A Study of Things",
        authors=[Author("Krushna Parmar", "DA-IICT")],
        abstract="A short abstract.",
        body=r"\section{Introduction}" "\n" "Some text.",
    )
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(render(doc))

    pdf, log = compile_pdf(tex_path, tmp_path)
    assert pdf.exists(), f"IEEEtran rejected the output:\n{log}"


@needs_tectonic
def test_rendered_document_passes_its_own_checks(tmp_path):
    """A paper we generated should not fail our own compliance rules."""
    from prarup.checks import run_all_checks
    from prarup.compile import compile_pdf
    from prarup.models import Rules

    doc = Document(title="T", authors=[Author("A", "B")],
                   abstract="Short.", body=r"\section{Intro}" "\nText.")
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(render(doc))

    pdf, _ = compile_pdf(tex_path, tmp_path)
    assert run_all_checks(pdf, Rules()) == []

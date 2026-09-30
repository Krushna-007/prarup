"""Integration tests. These run the real Tectonic binary, so they are slow
and are skipped when it is not installed."""

import shutil
from pathlib import Path

import pytest

from prarup.compile import compile_pdf

needs_tectonic = pytest.mark.skipif(
    shutil.which("tectonic") is None, reason="tectonic not installed"
)

MINIMAL_TEX = r"""
\documentclass{article}
\begin{document}
Hello.
\end{document}
"""


@needs_tectonic
def test_compiles_a_minimal_document(tmp_path):
    tex = tmp_path / "paper.tex"
    tex.write_text(MINIMAL_TEX)

    pdf, log = compile_pdf(tex, tmp_path / "build")

    assert pdf.exists()
    assert pdf.stat().st_size > 0

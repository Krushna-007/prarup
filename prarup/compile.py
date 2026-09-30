"""Compile a LaTeX file with Tectonic.

This file runs an external program, so it lives outside checks.py.
"""

import shutil
import subprocess
from pathlib import Path


class TectonicNotFound(Exception):
    """Raised when the tectonic binary is not on PATH."""


def compile_pdf(tex_path: Path, out_dir: Path) -> tuple[Path, str]:
    """Build a PDF and return its path together with the compiler log.

    Raises TectonicNotFound if tectonic is not installed, which is a
    clearer failure than whatever subprocess would report.
    """
    if shutil.which("tectonic") is None:
        raise TectonicNotFound(
            "tectonic is not installed. Install it with: brew install tectonic"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["tectonic", "--synctex", "--outdir", str(out_dir), str(tex_path)],
        capture_output=True,
        text=True,
    )

    pdf_path = out_dir / (tex_path.stem + ".pdf")
    return pdf_path, result.stderr

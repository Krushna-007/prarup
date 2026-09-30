"""Automatic repairs.

Only repairs that are unambiguous belong here. Anything that changes what
the paper says is the author's decision, not ours.
"""

import shutil
import subprocess
from pathlib import Path


class GhostscriptNotFound(Exception):
    """Raised when the gs binary is not on PATH."""


class RepairFailed(Exception):
    """Raised when Ghostscript runs but produces nothing usable."""


def embed_fonts(pdf_path: Path, out_path: Path) -> Path:
    """Rewrite a PDF with every referenced font embedded.

    This repairs FONT-01 and nothing else. Ghostscript cannot convert a
    Type3 bitmap font into outlines, and it cannot invent a font that is
    missing from the system entirely. In both cases it exits zero and
    returns a file that still fails, which is why the caller must re-run
    the check rather than trusting the exit code.
    """
    if shutil.which("gs") is None:
        raise GhostscriptNotFound(
            "ghostscript is not installed. Install it with: brew install ghostscript"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "gs",
            "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dQUIET",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-dEmbedAllFonts=true",
            "-dSubsetFonts=true",
            "-dMaxSubsetPct=100",
            f"-sOutputFile={out_path}",
            str(pdf_path),
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not out_path.exists():
        raise RepairFailed(result.stderr.strip() or "ghostscript produced no output")

    return out_path

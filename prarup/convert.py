"""Turn a .docx manuscript into LaTeX using pandoc.

Runs an external program, so it lives outside checks.py.
"""

import shutil
import subprocess
from pathlib import Path


class PandocNotFound(Exception):
    """Raised when the pandoc binary is not on PATH."""


class ConversionFailed(Exception):
    """Raised when pandoc runs but reports an error."""


def docx_to_tex(docx_path: Path, out_dir: Path) -> Path:
    """Convert a .docx to LaTeX and return the path of the .tex file.

    --extract-media is not optional. Without it pandoc still writes
    \\includegraphics for every image, but never creates the file it points
    at, so the document compiles with the figures silently missing.

    The argument has to be "." rather than a directory name. pandoc appends
    its own "media" folder to whatever you give it, so --extract-media=media
    produces media/media/rId9.png while the .tex refers to media/rId9.png.
    """
    if shutil.which("pandoc") is None:
        raise PandocNotFound(
            "pandoc is not installed. Install it with: brew install pandoc"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / (docx_path.stem + ".tex")

    result = subprocess.run(
        [
            "pandoc",
            str(docx_path.resolve()),
            "-t", "latex",
            "--extract-media=.",
            "-o", tex_path.name,
        ],
        cwd=out_dir,          # so extracted media lands beside the .tex
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ConversionFailed(result.stderr.strip())

    return tex_path


def find_custom_macros(tex_source: str) -> list[str]:
    """Return the names of any custom macros defined in the source.

    pandoc cannot resolve these, so equations built from them may be lost
    or corrupted. We warn rather than fail.
    """
    import re

    pattern = r"\\(?:new|renew|provide)command\s*\{?\\(\w+)"
    return re.findall(pattern, tex_source)

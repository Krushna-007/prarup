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


def docx_to_tex(docx_path: Path, out_dir: Path, standalone: bool = True) -> Path:
    """Convert a .docx to LaTeX and return the path of the .tex file.

    --extract-media is not optional. Without it pandoc still writes
    \\includegraphics for every image, but never creates the file it points
    at, so the document compiles with the figures silently missing.

    The argument has to be "." rather than a directory name. pandoc appends
    its own "media" folder to whatever you give it, so --extract-media=media
    produces media/media/rId9.png while the .tex refers to media/rId9.png.

    standalone controls whether pandoc wraps the output in a document
    preamble. Pass True to get something that compiles on its own; pass
    False to get a body fragment for the IEEE template to wrap, which is
    what the build pipeline uses.
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
            *(["--standalone"] if standalone else []),
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


# pandoc writes these into its own standalone preamble. They belong to
# pandoc, not to the author, and warning about them is pure noise.
PANDOC_MACROS = {
    "tightlist", "xmpquote", "passthrough", "pandocbounded",
    "real", "oldparagraph", "oldsubparagraph",
}


def find_custom_macros(tex_source: str) -> list[str]:
    """Return the author's own macro definitions found in the source.

    pandoc cannot resolve custom macros, so equations built from them may
    be lost or corrupted. The caller warns rather than failing.
    """
    import re

    pattern = r"\\(?:new|renew|provide)command\s*\*?\s*\{?\\(\w+)"
    found = re.findall(pattern, tex_source)
    return [name for name in found if name not in PANDOC_MACROS]

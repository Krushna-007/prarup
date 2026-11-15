"""Talk to pandoc through its JSON document tree.

pandoc reads Word and LaTeX into the same tree, which is what lets one
editor and one checker serve both. Conversions are batched: many pieces
go through a single pandoc run, separated by a marker paragraph, because
one run per block would take seconds on a real paper.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

SEPARATOR = "PRARUPSEPARATOR"


class PandocNotFound(Exception):
    """Raised when the pandoc binary is not on PATH."""


class PandocFailed(Exception):
    """Raised when pandoc runs but cannot read or write the document."""


def _run(args: list[str], cwd: Path | None = None, stdin: str | None = None) -> str:
    if shutil.which("pandoc") is None:
        raise PandocNotFound("pandoc is not installed. Install it with: brew install pandoc")
    result = subprocess.run(["pandoc", *args], cwd=cwd, input=stdin,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise PandocFailed(result.stderr.strip() or "pandoc failed")
    return result.stdout


def read(path: Path, media_dir: Path | None = None) -> dict:
    """Read a .docx or .tex into pandoc's JSON tree.

    For a .docx, images are written into media_dir/media/. A .tex is read
    from its own folder so \\input files and relative image paths resolve.
    """
    path = Path(path).resolve()
    fmt = "docx" if path.suffix.lower() == ".docx" else "latex"
    args = [str(path), "-f", fmt, "-t", "json"]
    if fmt == "docx" and media_dir is not None:
        media_dir.mkdir(parents=True, exist_ok=True)
        return json.loads(_run(args + ["--extract-media=."], cwd=media_dir))
    return json.loads(_run(args, cwd=path.parent))


_BLOCKS = {"Para", "Plain", "Header", "BlockQuote", "CodeBlock", "LineBlock"}


def stringify(node) -> str:
    """Plain text of any pandoc node or list of nodes."""
    out = []

    def walk(n):
        if isinstance(n, dict):
            kind = n.get("t")
            if kind == "Str":
                out.append(n["c"])
            elif kind in ("Space", "SoftBreak"):
                out.append(" ")
            elif kind == "LineBreak":
                out.append("\n")
            elif kind == "Math":
                out.append(n["c"][1])
            elif kind == "Code":
                out.append(n["c"][1])
            elif kind in ("Image", "Note"):
                pass
            elif kind in _BLOCKS:
                walk(n.get("c"))
                out.append("\n")             # keep table cells and paragraphs apart
            elif kind == "Quoted":
                out.append("“")
                walk(n["c"][1])
                out.append("”")
            else:
                walk(n.get("c"))
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return "\n".join(" ".join(line.split()) for line in "".join(out).split("\n")
                     if line.strip()).strip()


def _batch(pieces: list[list], api: list, to: str, extra: list[str] = ()) -> list[str]:
    """Convert lists of blocks, all in one pandoc run."""
    if not pieces:
        return []
    blocks = []
    for piece in pieces:
        blocks += piece
        blocks.append({"t": "Para", "c": [{"t": "Str", "c": SEPARATOR}]})
    doc = {"pandoc-api-version": api, "meta": {}, "blocks": blocks}
    text = _run(["-f", "json", "-t", to, "--wrap=none", *extra], stdin=json.dumps(doc))
    parts = text.split(SEPARATOR)
    return [p.strip() for p in parts[:len(pieces)]]


def blocks_to(pieces: list[list], api: list, to: str, extra: list[str] = ()) -> list[str]:
    """Each list of blocks as text in format `to` (markdown, latex, plain)."""
    return _batch(pieces, api, to, extra)


def inlines_to(pieces: list[list], api: list, to: str, extra: list[str] = ()) -> list[str]:
    """Each list of inlines (a caption, a title) as text in format `to`."""
    return _batch([[{"t": "Plain", "c": p}] for p in pieces], api, to, extra)


def markdown_to_blocks(texts: list[str], api: list) -> list[list]:
    """Parse edited Markdown back into pandoc blocks, one list per text."""
    if not texts:
        return []
    source = f"\n\n{SEPARATOR}\n\n".join(texts)
    doc = json.loads(_run(["-f", "markdown", "-t", "json"], stdin=source))
    groups, current = [], []
    for block in doc["blocks"]:
        if block.get("t") == "Para" and stringify(block) == SEPARATOR:
            groups.append(current)
            current = []
        else:
            current.append(block)
    groups.append(current)
    return groups


def _one_line(text: str) -> str:
    """A caption or title as one paragraph: "a. Results" must not become a list."""
    text = re.sub(r"^([-*+#>])", r"\\\1", " ".join(text.split()))
    return re.sub(r"^([A-Za-z0-9]{1,3})([.)])(\s)", r"\1\\\2\3", text)


def markdown_to_latex(texts: list[str]) -> list[str]:
    """Convert short Markdown texts (captions, titles) to LaTeX in one run."""
    if not texts:
        return []
    source = f"\n\n{SEPARATOR}\n\n".join(_one_line(t) if t.strip() else "​" for t in texts)
    out = _run(["-f", "markdown", "-t", "latex", "--wrap=none"], stdin=source)
    return [p.strip().replace("​", "") for p in out.split(SEPARATOR)][:len(texts)]


def latex_to_markdown(texts: list[str]) -> list[str]:
    """Convert LaTeX snippets (bibliography entries) to Markdown in one run."""
    if not texts:
        return []
    source = f"\n\n{SEPARATOR}\n\n".join(texts)
    out = _run(["-f", "latex", "-t", "markdown", "--wrap=none"], stdin=source)
    return [" ".join(p.split()) for p in out.split(SEPARATOR)][:len(texts)]

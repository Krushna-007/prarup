import json
import re
from pathlib import Path

from prarup.process import find_tool, run_tool

SEPARATOR = "PRARUPSEPARATOR"


class PandocNotFound(Exception):
    pass


class PandocFailed(Exception):
    pass


def _run(args: list[str], cwd: Path | None = None, stdin: str | None = None) -> str:
    pandoc = find_tool("pandoc")
    if not pandoc:
        raise PandocNotFound("pandoc is not installed or is missing from PATH.")
    result = run_tool([pandoc, *args], cwd=cwd, input=stdin)
    if result.returncode != 0:
        raise PandocFailed(result.stderr.strip() or "pandoc failed")
    return result.stdout


def read(path: Path, media_dir: Path | None = None) -> dict:
    path = Path(path).resolve()
    fmt = "docx" if path.suffix.lower() == ".docx" else "latex"
    args = [str(path), "-f", fmt, "-t", "json"]
    if fmt == "docx" and media_dir is not None:
        media_dir.mkdir(parents=True, exist_ok=True)
        return json.loads(_run(args + ["--extract-media=."], cwd=media_dir))
    return json.loads(_run(args, cwd=path.parent))


_BLOCKS = {"Para", "Plain", "Header", "BlockQuote", "CodeBlock", "LineBlock"}


def table_rows(table):
    _, _, _, head, bodies, foot = table["c"]
    rows = list(head[1])
    for body in bodies:
        rows += body[2] + body[3]
    return rows + foot[1], len(head[1])


def stringify(node) -> str:
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
                out.append("\n")
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


def blocks_to(pieces: list[list], api: list, to: str) -> list[str]:
    if not pieces:
        return []
    blocks = []
    for piece in pieces:
        blocks += piece
        blocks.append({"t": "Para", "c": [{"t": "Str", "c": SEPARATOR}]})
    doc = {"pandoc-api-version": api, "meta": {}, "blocks": blocks}
    text = _run(["-f", "json", "-t", to, "--wrap=none"], stdin=json.dumps(doc))
    parts = text.split(SEPARATOR)
    return [p.strip() for p in parts[:len(pieces)]]


def markdown_to_blocks(texts: list[str]) -> list[list]:
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
    text = re.sub(r"^([-*+#>])", r"\\\1", " ".join(text.split()))
    return re.sub(r"^([A-Za-z0-9]{1,3})([.)])(\s)", r"\1\\\2\3", text)


def markdown_to_latex(texts: list[str]) -> list[str]:
    filled = [t for t in texts if t.strip()]
    if not filled:
        return ["" for _ in texts]
    source = f"\n\n{SEPARATOR}\n\n".join(_one_line(t) for t in filled)
    out = _run(["-f", "markdown", "-t", "latex", "--wrap=none"], stdin=source)
    converted = iter(p.strip() for p in out.split(SEPARATOR))
    return [next(converted) if t.strip() else "" for t in texts]


def latex_to_markdown(texts: list[str]) -> list[str]:
    if not texts:
        return []
    source = f"\n\n{SEPARATOR}\n\n".join(texts)
    out = _run(["-f", "latex", "-t", "markdown", "--wrap=none"], stdin=source)
    return [" ".join(p.split()) for p in out.split(SEPARATOR)][:len(texts)]

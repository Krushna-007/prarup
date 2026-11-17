"""Damage real papers on purpose, so every check has something real to find.

Writes tests/fixtures/messy/. Each damage is listed in the MANIFEST below
and in tests/fixtures/messy/README.md, together with the finding it must
produce. Run from the project root:

    poetry run python tools/make_messy.py

Word papers are damaged through pandoc's document tree (read, edit,
write back as .docx), so the result is an ordinary Word file. Images go in
byte for byte, so the AI image keeps its signed C2PA manifest.
"""

import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
OUT = FIX / "messy"
AI_IMAGE = FIX / "images" / "gemini_c2pa.jpg"


def stringify(node) -> str:
    out = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("t") == "Str":
                out.append(n["c"])
            elif n.get("t") in ("Space", "SoftBreak"):
                out.append(" ")
            else:
                walk(n.get("c"))
        elif isinstance(n, list):
            for x in n:
                walk(x)
    walk(node)
    return "".join(out)


def para(text: str) -> dict:
    words = text.split(" ")
    inlines = []
    for i, w in enumerate(words):
        if i:
            inlines.append({"t": "Space"})
        inlines.append({"t": "Str", "c": w})
    return {"t": "Para", "c": inlines}


def image_para(path: Path, width: str = "3in") -> dict:
    return {"t": "Para", "c": [{"t": "Image", "c": [["", [], [["width", width]]], [],
                                                     [str(path), ""]]}]}


def damage_docx(source: Path, target: Path, steps: list) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        doc = json.loads(subprocess.run(
            ["pandoc", str(source), "-t", "json", "--extract-media=."],
            cwd=tmp, capture_output=True, text=True, check=True).stdout)
        for step in steps:
            step(doc["blocks"], tmp)
        (tmp / "doc.json").write_text(json.dumps(doc))
        subprocess.run(["pandoc", "doc.json", "-f", "json", "-o", str(target)],
                       cwd=tmp, check=True)


# ---------------------------------------------------------------- damage steps

def drop_captions(*numbers):
    """Delete the caption paragraph of the given figures ("Figure 2. ...")."""
    def step(blocks, _):
        for n in numbers:
            for i, b in enumerate(blocks):
                text = stringify(b)
                if b["t"] == "Para" and text.startswith((f"Figure {n}.", f"Figure {n}:")):
                    del blocks[i]
                    break
    return step


def drop_front_matter_text(*starts):
    """Delete paragraphs (or layout tables) that start with any of the given words."""
    def step(blocks, _):
        blocks[:] = [b for b in blocks
                     if not stringify(b).replace(" ", "").upper().startswith(
                         tuple(s.replace(" ", "").upper() for s in starts))]
    return step


def downscale_image(index: int, width_px: int):
    """Shrink the index-th embedded image (in reading order) to width_px."""
    def step(blocks, tmp):
        found = []

        def walk(n):
            if isinstance(n, dict):
                if n.get("t") == "Image":
                    found.append(n)
                walk(n.get("c"))
            elif isinstance(n, list):
                for x in n:
                    walk(x)
        walk(blocks)
        image = found[index]
        path = tmp / image["c"][2][0]
        with Image.open(path) as im:
            small = im.convert("RGB").resize((width_px, round(im.height * width_px / im.width)))
        small_path = path.with_name("lowres_" + path.stem + ".png")
        small.save(small_path)
        image["c"][2][0] = str(small_path.relative_to(tmp))
    return step


def insert_after_heading(heading: str, blocks_to_add):
    """Insert after the block whose whole text is the heading (case ignored)."""
    def step(blocks, tmp):
        at = next(i for i, b in enumerate(blocks)
                  if stringify(b).strip().lower() == heading.lower())
        new = blocks_to_add(tmp)
        blocks[at + 1:at + 1] = new
    return step


def ai_figure(caption: str):
    def make(tmp):
        target = tmp / "media" / "overview.jpg"
        target.parent.mkdir(exist_ok=True)
        shutil.copy(AI_IMAGE, target)                       # byte for byte: C2PA survives
        return [image_para(Path("media/overview.jpg"), "3in"), para(caption)]
    return make


def duplicate_figure(of_figure: int, caption: str):
    """Insert a second copy of the image captioned "Figure <of_figure>.", with its own caption."""
    def make(tmp, blocks):
        for i, b in enumerate(blocks):
            if stringify(b).startswith((f"Figure {of_figure}.", f"Figure {of_figure}:")):
                image = blocks[i - 1]["c"][0]["c"][2][0]
                return [image_para(Path(image), "3in"), para(caption)]
        raise ValueError(f"no Figure {of_figure} caption")
    return make


def insert_duplicate_after(heading: str, make):
    def step(blocks, tmp):
        new = make(tmp, blocks)
        at = next(i for i, b in enumerate(blocks)
                  if stringify(b).strip().lower() == heading.lower())
        blocks[at + 1:at + 1] = new
    return step


def cite_missing_reference(number: int, after: str = "Introduction"):
    """Add "[number]." to the first long paragraph after the given heading."""
    def step(blocks, _):
        start = next(i for i, b in enumerate(blocks) if stringify(b).strip().lower() == after.lower())
        target = next(b for b in blocks[start:] if b["t"] == "Para" and len(stringify(b)) > 200)
        target["c"] += [{"t": "Space"}, {"t": "Str", "c": f"[{number}]."}]
    return step


# ---------------------------------------------------------------- LaTeX

def damage_latex(target: Path) -> None:
    """The LaTeX project, zipped, with a caption removed, an AI figure, a
    low-resolution figure and a duplicate."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp) / "paper"
        shutil.copytree(FIX / "latex_project", tmp)
        shutil.copy(AI_IMAGE, tmp / "figs" / "overview.jpg")
        with Image.open(tmp / "figs" / "accuracy.png") as im:
            im.resize((240, round(im.height * 240 / im.width))).save(tmp / "figs" / "loss.png")
        main = tmp / "main.tex"
        text = main.read_text()
        text = text.replace("\\caption{Accuracy over rounds.}\n", "")
        extra = (
            "\\begin{figure}[htbp]\\centering\\includegraphics[width=\\columnwidth]{figs/overview}"
            "\\caption{Overview of the system.}\\label{fig:overview}\\end{figure}\n"
            "\\begin{figure}[htbp]\\centering\\includegraphics[width=\\columnwidth]{figs/loss}"
            "\\caption{Training loss.}\\label{fig:loss}\\end{figure}\n"
            "\\begin{figure}[htbp]\\centering\\includegraphics[width=\\columnwidth]{figs/accuracy}"
            "\\caption{Accuracy again, for comparison.}\\end{figure}\n"
            "Fig.~\\ref{fig:overview} and Fig.~\\ref{fig:loss} summarise the results.\n"
        )
        main.write_text(text.replace("\\begin{thebibliography}", extra + "\\begin{thebibliography}"))
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for f in tmp.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(tmp))


MANIFEST = {
    "svm_messy.docx": (FIX / "real" / "svm_diabetes.docx", [
        insert_duplicate_after("Experimental result",
                               duplicate_figure(3, "Figure 10. The developed model, again.")),
        drop_captions(2),
        drop_front_matter_text("A B S T R A C T", "ABSTRACT"),
        downscale_image(1, 400),
        insert_after_heading("Proposed method", ai_figure("Figure 9. Overview of the proposed pipeline.")),
    ]),
    "uav_messy.docx": (FIX / "real" / "uav_imagery.docx", [
        drop_captions(1),
        drop_front_matter_text("Keywords"),
        cite_missing_reference(99),
    ]),
}


def main() -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc is needed")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (source, steps) in MANIFEST.items():
        damage_docx(source, OUT / name, steps)
        print("wrote", OUT / name)
    damage_latex(OUT / "latex_messy.zip")
    print("wrote", OUT / "latex_messy.zip")


if __name__ == "__main__":
    main()

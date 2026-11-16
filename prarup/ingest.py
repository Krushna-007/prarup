import re
import shutil
import zipfile
from pathlib import Path

from prarup import pandoc, texsource
from prarup.frontmatter import latex_to_plain, read_authors, title_and_authors
from prarup.manuscript import Block, Manuscript

_FIG_CAPTION = re.compile(
    r"^\s*(?:fig(?:ure)?s?)\.?\s*(\d+)\s*(?:[a-z](?:\s*(?:,|and|&)\s*[a-z])*)?\s*[:.\-–—]?\s*(.*)$",
    re.I | re.S)


_STRICT_CAPTION = re.compile(r"^\s*(?:fig(?:ure)?s?)\.?\s*\d+\s*[a-z]?\s*[:.\-–—]\s+\S", re.I)
_TAB_CAPTION = re.compile(r"^\s*table\s*(\d+|[IVX]+)\s*[:.\-–—]?\s*(.*)$", re.I | re.S)
_REFERENCES = re.compile(r"^\s*(references?|bibliography|reference list|works cited)\s*:?\s*$", re.I)
_ABSTRACT = re.compile(r"^\s*abstract\b[\s:.\-–—]*(.*)$", re.I | re.S)
_KEYWORDS = re.compile(r"^\s*(?:keywords?|key words|index terms)\b[\s:.\-–—]*(.*)$", re.I | re.S)
_EQ_NUMBER = re.compile(r"^\(\s*\d+\s*\)$")
IMAGE_EXTENSIONS = ["", ".pdf", ".png", ".jpg", ".jpeg", ".eps"]


class OpenFailed(Exception):
    pass


def _unspace(text: str) -> str:
    return re.sub(r"\b(?:[A-Z] ){2,}[A-Z]\b", lambda m: m.group().replace(" ", ""), text)


def _images(node) -> list[tuple[str, dict]]:
    found = []

    def walk(n):
        if isinstance(n, dict):
            if n.get("t") == "Image":
                attrs = dict(n["c"][0][2])
                found.append((n["c"][2][0], attrs))
            else:
                walk(n.get("c"))
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return found


def _image_only(block: dict) -> list:
    if block.get("t") not in ("Para", "Plain"):
        return []
    images, words = [], 0
    for inline in block["c"]:
        kind = inline.get("t")
        if kind == "Image":
            images.append(inline)
        elif kind == "Str":
            words += 1 if not re.fullmatch(r"\(?[a-z]\)?[.:]?", inline["c"]) else 0
        elif kind not in ("Space", "SoftBreak", "LineBreak"):
            words += 1
    return images if images and words == 0 else []


def _bold_heading(block: dict) -> list | None:
    if block.get("t") not in ("Para", "Plain"):
        return None
    inner = [i for i in block["c"] if i.get("t") not in ("Space", "SoftBreak")]
    if not inner or not all(i.get("t") == "Strong" for i in inner):
        return None
    text = pandoc.stringify(block)
    if not 2 <= len(text) <= 90 or text.endswith((".", ",", ";")) or _FIG_CAPTION.match(text):
        return None
    return [x for i in inner for x in i["c"]]


_SECTION_NAMES = re.compile(
    r"^\s*(?:\d+\.?\s*|[IVX]+\.\s*)?(introduction|background|related work|literature review|"
    r"methodology|methods?|proposed method|materials and methods|system model|experiments?|"
    r"experimental (?:setup|results?)|evaluation|results?(?: and discussion)?|discussion|"
    r"conclusions?(?: and future work)?|future work|acknowledge?ments?|appendix)\s*:?\s*$", re.I)


def _named_section(block: dict) -> str | None:
    if block.get("t") not in ("Para", "Plain"):
        return None
    text = pandoc.stringify(block)
    return text.rstrip(":").strip() if _SECTION_NAMES.match(text) else None


def _equation(block: dict) -> str | None:
    if block.get("t") not in ("Para", "Plain"):
        return None
    maths = [i for i in block["c"] if i.get("t") == "Math"]
    rest = [i for i in block["c"] if i.get("t") not in ("Math", "Space", "SoftBreak")]
    if len(maths) != 1 or any(i.get("t") != "Str" or not _EQ_NUMBER.match(i["c"]) for i in rest):
        return None
    if maths[0]["c"][0]["t"] != "DisplayMath" and not rest:
        return None
    return maths[0]["c"][1].strip()


def _flatten(blocks: list) -> list:
    out = []
    for block in blocks:
        if block.get("t") == "Div":
            classes = block["c"][0][1]
            if {"IEEEkeywords", "thebibliography"} & set(classes) or block["c"][0][0] == "refs":
                out.append(block)
            else:
                out += _flatten(block["c"][1])
        else:
            out.append(block)
    return out


def _main_tex(folder: Path) -> Path:
    for tex in sorted(folder.rglob("*.tex"), key=lambda p: len(p.parts)):
        text = tex.read_text(encoding="utf-8", errors="replace")
        if "\\documentclass" in text and "\\begin{document}" in text:
            return tex
    raise OpenFailed("no .tex file with \\documentclass and \\begin{document} in the archive")


def _unzip(archive: Path, into: Path) -> Path:
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (into / member.filename).resolve()
            if not str(target).startswith(str(into.resolve())):
                raise OpenFailed(f"unsafe path in archive: {member.filename}")
        z.extractall(into)
    return _main_tex(into)


def _front_matter(blocks: list, m: Manuscript) -> int:
    window = blocks[:30]
    texts = [_unspace(pandoc.stringify(b)) for b in window]
    where = None
    for i, (block, text) in enumerate(zip(window, texts)):
        if block.get("t") == "Header" and i > 0:
            break
        if _ABSTRACT.match(text) or (block.get("t") == "Table" and "ABSTRACT" in text.upper()):
            where = i
            break

    if where is None:
        end = next((i for i, b in enumerate(window) if b.get("t") == "Header"
                    or _bold_heading(b) and i > 0 and _REFERENCES.match(texts[i]) is None
                    and i > 2), len(window))
        head = [t for b, t in zip(window[:end], texts[:end]) if not _image_only(b)]
        if 0 < len(head) <= 8 and all(len(t) < 300 for t in head):
            m.title, m.authors = title_and_authors(head)
            m.notes.append("No abstract found; the first paragraphs were read as title and authors.")
            return end
        return 0

    used = where + 1
    if window[where].get("t") == "Table":
        cells = [_unspace(c) for c in pandoc.stringify(window[where]).split("\n")]
        prose = [c for c in cells if len(c) > 200]
        m.abstract = max(prose, key=len) if prose else ""
        for n, cell in enumerate(cells):
            found = _KEYWORDS.match(cell)
            if found:
                m.keywords = found.group(1).strip() or (cells[n + 1] if n + 1 < len(cells) else "")
                break
        m.notes.append("The abstract was inside a layout table and was taken out of it.")
    else:
        rest = _ABSTRACT.match(texts[where]).group(1).strip()
        if not rest and used < len(window):
            rest = texts[used]
            used += 1
        m.abstract = " ".join(rest.split())

    if used < len(window) and _KEYWORDS.match(texts[used]):
        m.keywords = " ".join(_KEYWORDS.match(texts[used]).group(1).split())
        used += 1

    logos = [b for b in window[:where] if _image_only(b)]
    if logos:
        m.notes.append(f"Left out {len(logos)} image(s) above the title (logos).")
    paragraphs = [pandoc.blocks_to([[b]], m.api, "plain")[0] if b.get("t") != "Header"
                  else texts[i] for i, b in enumerate(window[:where]) if not _image_only(b)]
    m.title, m.authors = title_and_authors(paragraphs)
    return used


_SUPER = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SYMBOLS = {r"\ddagger": "‡", r"\dagger": "†", r"\S": "§", r"\|": "‖", "||": "‖", "*": "*"}


def _marks_to_unicode(latex: str) -> str:
    def convert(match: re.Match) -> str:
        inner = match.group(1)
        out = re.sub(r"\d", lambda d: d.group().translate(_SUPER), re.sub(r"[(){},\s]", "", inner))
        for macro, symbol in _SYMBOLS.items():
            out = out.replace(macro, symbol)
        return out
    latex = re.sub(r"\$\s*\^\s*\{?(.*?)\}?\s*\$", convert, latex)
    return re.sub(r"\\textsuperscript\{([^}]*)\}", convert, latex)


def _tex_front_matter(doc: dict, main: Path, m: Manuscript) -> None:
    meta = doc.get("meta", {})
    if "title" in meta:
        m.title = pandoc.stringify(meta["title"])
    if "abstract" in meta:
        m.abstract = " ".join(pandoc.stringify(meta["abstract"]).split())
    source = texsource.full_source(main)
    blocks = texsource.ieee_author_blocks(source)
    paragraphs = [latex_to_plain(_marks_to_unicode(names))
                  + ("\n" + latex_to_plain(_marks_to_unicode(place)) if place else "")
                  for names, place in blocks]
    m.authors = read_authors(paragraphs) if paragraphs else []


def _resolve(path: str, folder: Path) -> tuple[Path | None, str]:
    for ext in IMAGE_EXTENSIONS:
        candidate = folder / (path + ext)
        if candidate.is_file():
            actual = {f.name.lower(): f.name for f in candidate.parent.iterdir()}
            real = actual.get(candidate.name.lower(), candidate.name)
            if real != candidate.name:
                return candidate.parent / real, (f"'{path}' only matches '{real}' if case is "
                                                 f"ignored; it breaks on Linux")
            return candidate, ""
    parent = (folder / path).parent
    stem = Path(path).name.lower()
    if parent.is_dir():
        for f in parent.iterdir():
            if f.name.lower() in (stem + e for e in IMAGE_EXTENSIONS) and f.is_file():
                return f, f"'{path}' only matches '{f.name}' if case is ignored; it breaks on Linux"
    return None, ""


def _bring_inline_images(m: Manuscript, folder: Path, project: Path) -> None:
    def walk(n):
        if isinstance(n, dict):
            if n.get("t") == "Image":
                found, _ = _resolve(n["c"][2][0], folder)
                if found is not None:
                    target = project / "media" / found.name
                    if not target.exists():
                        shutil.copy2(found, target)
                    n["c"][2][0] = f"media/{found.name}"
            else:
                walk(n.get("c"))
        elif isinstance(n, list):
            for item in n:
                walk(item)
    for block in m.blocks:
        if block.kind != "figure":
            walk(block.node)


def _bring_media(m: Manuscript, folder: Path, project: Path) -> None:
    media = project / "media"
    media.mkdir(parents=True, exist_ok=True)
    for block in m.figures():
        moved = []
        for path in block.images:
            found, note = _resolve(path, folder)
            if found is None:
                moved.append(path)
                continue
            target = media / found.name
            if not target.exists():
                shutil.copy2(found, target)
            moved.append(f"media/{found.name}")
            if note:
                m.notes.append(f"Figure image {note}.")
        block.images = moved


def _body(blocks: list, m: Manuscript, start_id: int = 1) -> list[Block]:
    out: list[Block] = []
    counter = [start_id]

    def add(**kw) -> Block:
        b = Block(id=f"b{counter[0]}", **kw)
        counter[0] += 1
        out.append(b)
        return b

    i = 0
    while i < len(blocks):
        block = blocks[i]
        kind = block.get("t")
        text = pandoc.stringify(block)
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        nxt_text = pandoc.stringify(nxt) if nxt else ""

        if kind == "Header" and _REFERENCES.match(text) or (
                kind in ("Para", "Plain") and _REFERENCES.match(text)):
            entries = []
            i += 1
            while i < len(blocks) and blocks[i].get("t") != "Header" and not _bold_heading(blocks[i]):
                if blocks[i].get("t") in ("OrderedList", "BulletList"):
                    entries += [item for item in blocks[i]["c"][-1]]
                else:
                    entries.append([blocks[i]])
                i += 1
            add(kind="references", text="References", node=[block], entries=entries)
            continue

        if kind == "Div":
            classes = block["c"][0][1]
            if "IEEEkeywords" in classes:
                m.keywords = " ".join(pandoc.stringify(block).split())
            else:
                add(kind="references", text="References", node=[block],
                    entries=[[b] for b in block["c"][1]])
            i += 1
            continue

        if kind == "Header":
            add(kind="heading", level=block["c"][0], node=[block], text=block["c"][2])
            i += 1
            continue

        named = _named_section(block)
        if named is not None:
            add(kind="heading", level=1, node=[block], text=[{"t": "Str", "c": named}],
                detected="section name on its own line")
            i += 1
            continue

        bold = _bold_heading(block)
        if bold is not None:
            add(kind="heading", level=1, node=[block], text=bold, detected="bold paragraph")
            i += 1
            continue

        if kind == "Figure":
            images = _images(block["c"][2])
            caption = block["c"][1][1]
            add(kind="figure", node=[block], images=[p for p, _ in images],
                widths=[a.get("width", "") for _, a in images],
                caption=caption, label=block["c"][0][0])
            i += 1
            continue

        pictures = _image_only(block)
        if pictures:
            group = [block]
            while i + len(group) < len(blocks) and _image_only(blocks[i + len(group)]):
                group.append(blocks[i + len(group)])
            images = [img for g in group for img in _image_only(g)]
            after = blocks[i + len(group)] if i + len(group) < len(blocks) else None
            after_text = pandoc.stringify(after) if after else ""
            fig = add(kind="figure", node=group, images=[img["c"][2][0] for img in images],
                      widths=[dict(img["c"][0][2]).get("width", "") for img in images])
            match = _FIG_CAPTION.match(after_text) if after and after.get("t") in (
                "Para", "Plain", "BlockQuote", "Figure") else None
            if match and after.get("t") == "Figure":
                more = _images(after["c"][2])
                fig.images += [p for p, _ in more]
                fig.widths += [a.get("width", "") for _, a in more]
                fig.number, fig.caption, fig.label = int(match.group(1)), after["c"][1][1], after["c"][0][0]
                fig.detected = "sub-images joined to the captioned figure after them"
                fig.node = group + [after]
                i += len(group) + 1
            elif match:
                fig.number, fig.caption = int(match.group(1)), [after]
                fig.detected = "caption found in the paragraph after the image"
                fig.node = group + [after]
                i += len(group) + 1
            else:
                i += len(group)
            continue

        if (m.source.lower().endswith(".docx") and kind in ("Para", "Plain", "BlockQuote")
                and _STRICT_CAPTION.match(text) and len(text) < 400):
            match = _FIG_CAPTION.match(text)
            add(kind="figure", node=[block], images=[], caption=[block],
                number=int(match.group(1)), detected="a caption with no image above it")
            i += 1
            continue

        if kind == "Table":
            caption = block["c"][1][1]
            tab = add(kind="table", node=[block], caption=caption)
            if not pandoc.stringify(caption):
                before = out[-2] if len(out) > 1 else None
                if before and before.kind in ("para", "quote") and _TAB_CAPTION.match(
                        pandoc.stringify(before.node)):
                    tab.caption, tab.detected = before.node, "caption found in the paragraph before the table"
                    out.remove(before)
                elif nxt and nxt.get("t") in ("Para", "Plain", "BlockQuote") and _TAB_CAPTION.match(nxt_text):
                    tab.caption, tab.detected = [nxt], "caption found in the paragraph after the table"
                    i += 1
            i += 1
            continue

        equation = _equation(block)
        if equation is not None:
            add(kind="equation", node=[block], text=equation,
                detected="" if "DisplayMath" in str(block) else "inline maths numbered like an equation")
            i += 1
            continue

        mapping = {"Para": "para", "Plain": "para", "LineBlock": "para", "BlockQuote": "quote",
                   "BulletList": "list", "OrderedList": "list", "CodeBlock": "code",
                   "RawBlock": "raw", "DefinitionList": "list"}
        if kind != "HorizontalRule":
            add(kind=mapping.get(kind, "raw"), node=[block])
        i += 1
    return out


def _to_markdown(m: Manuscript) -> None:
    blocks, captions, entries = [], [], []
    for b in m.blocks:
        if b.kind == "heading":
            blocks.append([{"t": "Plain", "c": b.text}])
        elif b.kind not in ("equation", "figure", "references"):
            blocks.append(b.node)
        if b.kind in ("figure", "table"):
            captions.append(b.caption or [])
        if b.kind == "references":
            entries += b.entries

    texts = iter(pandoc.blocks_to(blocks, m.api, "markdown"))
    caps = iter(pandoc.blocks_to(captions, m.api, "markdown"))
    refs = iter(pandoc.blocks_to(entries, m.api, "markdown"))
    for b in m.blocks:
        if b.kind not in ("equation", "figure", "references"):
            b.text = next(texts)
        if b.kind in ("figure", "table"):
            caption = next(caps)
            caption = re.sub(r"^>\s?", "", caption, flags=re.M)
            pattern = _FIG_CAPTION if b.kind == "figure" else _TAB_CAPTION
            plain = re.sub(r"[*_]", "", caption)
            match = pattern.match(plain)
            if match:
                caption = match.group(2).strip()
                b.number = b.number or (int(match.group(1)) if match.group(1).isdigit() else 0)
            b.caption = " ".join(caption.split())
        if b.kind == "references":
            b.entries = [next(refs) for _ in b.entries]


def _tidy_paths(m: Manuscript) -> None:
    for b in m.figures():
        b.images = [p[2:] if p.startswith("./") else p for p in b.images]


def open_paper(path: Path, project: Path) -> Manuscript:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".docx", ".tex", ".zip"):
        raise OpenFailed(f"{path.name} is not a .docx, .tex or .zip file")
    project.mkdir(parents=True, exist_ok=True)

    main = _unzip(path, project / "source") if suffix == ".zip" else path
    doc = pandoc.read(main, media_dir=project if suffix == ".docx" else None)
    m = Manuscript(source=str(path), api=doc["pandoc-api-version"])
    blocks = _flatten(doc["blocks"])

    if suffix == ".docx":
        used = _front_matter(blocks, m)
        blocks = blocks[used:]
    else:
        _tex_front_matter(doc, main, m)
        if not m.title:
            used = _front_matter(blocks, m)
            blocks = blocks[used:]

    m.blocks = _body(blocks, m)
    _to_markdown(m)
    _tidy_paths(m)

    if suffix != ".docx":
        _bring_media(m, main.parent, project)
        _bring_inline_images(m, main.parent, project)
        source = texsource.full_source(main)
        m.preamble = texsource.preamble_extras(source)
        items = texsource.bibitems(source)
        bbl = main.with_suffix(".bbl")
        if not items and bbl.is_file():
            items = texsource.bibitems(bbl.read_text(encoding="utf-8", errors="replace"))
        for name in texsource.bibliography_files(source):
            bib = main.parent / (name if name.endswith(".bib") else f"{name}.bib")
            if bib.is_file():
                shutil.copy2(bib, project / "refs.bib")
                m.bibliography = "refs.bib"
                entries = texsource.bib_entries(bib.read_text(encoding="utf-8", errors="replace"))
                refs = next((b for b in m.blocks if b.kind == "references"), None)
                if refs is None:
                    refs = Block(id=f"b{len(m.blocks) + 1}", kind="references", text="References")
                    m.blocks.append(refs)
                refs.entries = pandoc.latex_to_markdown([texsource.describe_entry(f) for _, f in entries])
                refs.keys = [key for key, _ in entries]
                break
        if items and not m.bibliography:
            refs = next((b for b in m.blocks if b.kind == "references"), None)
            if refs is None:
                refs = Block(id=f"b{len(m.blocks) + 1}", kind="references", text="References")
                m.blocks.append(refs)
            refs.entries = pandoc.latex_to_markdown([text for _, text in items])
            refs.keys = [key for key, _ in items]
    return m

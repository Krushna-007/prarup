"""The paper as Prarup understands it: front matter and a list of blocks.

Every block keeps the pandoc node it came from, so whatever the user does
not edit is written back exactly as it was read. Edited text is held as
Markdown, which keeps emphasis, maths ($x^2$) and citations ([@key]).

Saved as JSON next to the paper, so edits survive closing the window.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from prarup.models import Author

# What the outline shows for each kind of block
TAGS = {
    "heading": "H", "para": "P", "figure": "FIG", "table": "TAB",
    "equation": "EQ", "list": "LIST", "quote": "QUOTE", "code": "CODE",
    "references": "REF", "raw": "RAW",
}


@dataclass
class Block:
    id: str
    kind: str                     # a key of TAGS
    text: str = ""                # Markdown: what the editor shows and edits
    level: int = 0                # heading level, 1 = section
    node: list = field(default_factory=list)   # original pandoc blocks
    edited: bool = False
    detected: str = ""            # how it was recognised, if not marked in the source
    # figures
    images: list = field(default_factory=list)   # paths inside the project folder
    caption: str = ""             # Markdown, without the "Figure 3:" prefix
    label: str = ""               # cross-reference label, if the source had one
    number: int = 0               # number the author gave it, 0 if none
    widths: list = field(default_factory=list)   # width the source asked for, inches
    fit_width: str = ""           # width chosen by the fitter, e.g. "0.62\\columnwidth"
    double: bool = False          # spans both columns (figure*)
    # references
    entries: list = field(default_factory=list)  # one Markdown string per reference
    keys: list = field(default_factory=list)     # citation key of each entry, if known


@dataclass
class Manuscript:
    source: str                   # path of the file the user opened
    title: str = ""
    authors: list = field(default_factory=list)  # list of Author
    abstract: str = ""
    keywords: str = ""
    blocks: list = field(default_factory=list)   # list of Block
    bibliography: str = ""        # .bib file inside the project folder, if any
    api: list = field(default_factory=list)      # pandoc-api-version
    notes: list = field(default_factory=list)    # what ingest noticed, for the user
    preamble: str = ""            # the author's maths packages and macros (LaTeX input)

    def figures(self) -> list:
        return [b for b in self.blocks if b.kind == "figure"]

    def tables(self) -> list:
        return [b for b in self.blocks if b.kind == "table"]

    def find(self, block_id: str) -> Block | None:
        return next((b for b in self.blocks if b.id == block_id), None)

    # ------------------------------------------------------------ storage

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1))

    @classmethod
    def load(cls, path: Path) -> "Manuscript":
        data = json.loads(Path(path).read_text())
        data["authors"] = [Author(**a) for a in data.get("authors", [])]
        data["blocks"] = [Block(**b) for b in data.get("blocks", [])]
        return cls(**data)

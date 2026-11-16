import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from prarup.models import Author


@dataclass
class Block:
    id: str
    kind: str
    text: str = ""
    level: int = 0
    node: list = field(default_factory=list)
    edited: bool = False
    detected: str = ""

    images: list = field(default_factory=list)
    caption: str = ""
    label: str = ""
    number: int = 0
    widths: list = field(default_factory=list)
    fit_width: str = ""
    double: bool = False

    entries: list = field(default_factory=list)
    keys: list = field(default_factory=list)


@dataclass
class Manuscript:
    source: str
    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    keywords: str = ""
    blocks: list = field(default_factory=list)
    bibliography: str = ""
    api: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    preamble: str = ""
    source_mtime: float = 0.0

    def figures(self) -> list:
        return [b for b in self.blocks if b.kind == "figure"]

    def tables(self) -> list:
        return [b for b in self.blocks if b.kind == "table"]

    def find(self, block_id: str) -> Block | None:
        return next((b for b in self.blocks if b.id == block_id), None)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1))

    @classmethod
    def load(cls, path: Path) -> "Manuscript":
        data = json.loads(Path(path).read_text())
        data["authors"] = [Author(**a) for a in data.get("authors", [])]
        data["blocks"] = [Block(**b) for b in data.get("blocks", [])]
        return cls(**data)

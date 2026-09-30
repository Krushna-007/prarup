"""Plain data holders. These classes hold values and do nothing else."""

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass
class Issue:
    """One problem found in a compiled PDF."""

    code: str           # short identifier, e.g. "FONT-01"
    message: str        # what to show the user
    severity: str       # "error" or "warning"
    can_fix: bool = False   # True when we can repair it automatically


@dataclass
class Rules:
    """What the target conference requires.

    Loaded from a YAML file so a new conference is a data change rather
    than a code change.
    """

    page_limit: int = 6
    columns: int = 2
    body_font_pt: float = 10.0

    @classmethod
    def load(cls, path: Path) -> "Rules":
        """Read a rules file. Unknown keys raise, so typos are loud."""
        data = yaml.safe_load(Path(path).read_text()) or {}

        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(
                f"unknown key(s) in {path}: {', '.join(unknown)}. "
                f"Valid keys are: {', '.join(sorted(known))}"
            )

        return cls(**data)


@dataclass
class Document:
    """A manuscript, independent of the file it came from."""

    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    sections: list = field(default_factory=list)
    figures: list = field(default_factory=list)

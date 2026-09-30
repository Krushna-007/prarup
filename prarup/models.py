"""Plain data holders. These classes hold values and do nothing else."""

from dataclasses import dataclass, field


@dataclass
class Issue:
    """One problem found in a compiled PDF."""

    code: str           # short identifier, e.g. "FONT-01"
    message: str        # what to show the user
    severity: str       # "error" or "warning"
    can_fix: bool = False   # True when we can repair it automatically


@dataclass
class Rules:
    """What the target conference requires."""

    page_limit: int = 6
    columns: int = 2
    body_font_pt: float = 10.0


@dataclass
class Document:
    """A manuscript, independent of the file it came from."""

    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    sections: list = field(default_factory=list)
    figures: list = field(default_factory=list)

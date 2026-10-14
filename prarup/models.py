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
    # Smallest printed text allowed inside a figure. Our choice, not an
    # IEEE rule, set just under IEEE's 8 pt footnotes. Note that a default
    # matplotlib figure (6.4 in wide, 10 pt text) printed one column wide
    # carries 5.5 pt text, so it fails this unless drawn smaller.
    min_figure_text_pt: float = 7.0

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
class Author:
    """One author and where they work."""

    name: str
    affiliation: str = ""


@dataclass
class Document:
    """A manuscript, independent of the file it came from.

    body holds LaTeX rather than a parsed section tree. Parsing LaTeX into
    a full structure is a large job on its own and buys us nothing here:
    every input path already produces LaTeX, and the template only needs
    to wrap it. Title, authors and abstract are pulled out separately
    because IEEEtran needs them in specific commands.
    """

    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    keywords: str = ""
    body: str = ""
    bibliography: str = ""
    figures: list = field(default_factory=list)


@dataclass
class Graphic:
    """One \\includegraphics in a LaTeX source, and where it sits."""

    index: int          # 1-based, in source order
    start: int          # span of the whole \includegraphics[...]{...}
    end: int
    options: str        # text between the square brackets, "" if none
    path: str
    env: str = ""       # "figure", "figure*", or "" when not in a float
    env_begin: tuple = (0, 0)   # span of \begin{figure} or \begin{figure*}
    env_end: tuple = (0, 0)     # span of the matching \end{...}
    reason: str = ""    # why it must not be resized; "" when it may be


@dataclass
class Measured:
    """Where one graphic landed in the compiled PDF, and how it reads.

    text_per_width is the printed size of the figure's small text, in
    points, per point of figure width. Text scales with the figure, so
    this one number predicts the text size at any width. None when no
    text could be measured.
    """

    index: int
    page: int                   # 1-based
    x0: float
    y0: float
    x1: float
    y1: float
    overflow: float = 0.0       # points past the column (or text block)
    text_per_width: float | None = None
    text_source: str = ""       # "vector" or "ocr"

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def text_pt(self) -> float | None:
        return None if self.text_per_width is None else self.text_per_width * self.width


@dataclass
class Geometry:
    """Page layout as LaTeX itself reported it, in points."""

    column: float
    text: float
    left: float
    gap: float

    def bounds(self, x0: float, double: bool) -> tuple[float, float]:
        """The horizontal space a figure starting at x0 is allowed to use."""
        if double or self.column >= self.text:
            return self.left, self.left + self.text
        if x0 < self.left + self.column:
            return self.left, self.left + self.column
        return self.left + self.column + self.gap, self.left + self.text


@dataclass
class FigureChange:
    """What the fitter did to one graphic, for the report."""

    index: int
    page: int
    width_before: float          # points, as printed
    width_after: float
    double_before: bool          # spans both columns
    double_after: bool
    overflow_before: float
    text_before: float | None    # printed size of the small text, points
    text_after: float | None
    note: str = ""               # why it was left alone, or what to do


@dataclass
class FitReport:
    """The outcome of fitting one paper."""

    changes: list
    pages_before: int
    pages_after: int
    page_limit: int
    fitted_tex: Path | None = None
    pdf: Path | None = None
    summary: str = ""

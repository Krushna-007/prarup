from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass
class Issue:
    code: str
    message: str
    severity: str
    can_fix: bool = False


@dataclass
class Rules:
    page_limit: int = 6
    columns: int = 2
    body_font_pt: float = 10.0

    min_figure_text_pt: float = 7.0

    @classmethod
    def load(cls, path: Path) -> "Rules":
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
    name: str
    affiliation: str = ""


@dataclass
class Graphic:
    index: int
    start: int
    end: int
    options: str
    path: str
    env: str = ""
    env_begin: tuple = (0, 0)
    env_end: tuple = (0, 0)
    reason: str = ""


@dataclass
class Measured:
    index: int
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    overflow: float = 0.0
    text_per_width: float | None = None
    text_source: str = ""

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def text_pt(self) -> float | None:
        return None if self.text_per_width is None else self.text_per_width * self.width


@dataclass
class Geometry:
    column: float
    text: float
    left: float
    gap: float

    def bounds(self, x0: float, double: bool) -> tuple[float, float]:
        if double or self.column >= self.text:
            return self.left, self.left + self.text
        if x0 < self.left + self.column:
            return self.left, self.left + self.column
        return self.left + self.column + self.gap, self.left + self.text


@dataclass
class FigureChange:
    index: int
    page: int
    width_before: float
    width_after: float
    double_before: bool
    double_after: bool
    overflow_before: float
    text_before: float | None
    text_after: float | None
    note: str = ""
    name: str = ""


@dataclass
class FitReport:
    changes: list
    pages_before: int
    pages_after: int
    page_limit: int
    fitted_tex: Path | None = None
    pdf: Path | None = None
    summary: str = ""
    policy: str = "readable"
    min_pt: float = 7.0

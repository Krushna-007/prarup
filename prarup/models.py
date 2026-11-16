from pathlib import Path

import yaml


class Issue:
    def __init__(self, code, message, severity, can_fix=False):
        self.code = code
        self.message = message
        self.severity = severity
        self.can_fix = can_fix


class Rules:
    def __init__(self, page_limit=6, columns=2, body_font_pt=10.0, min_figure_text_pt=7.0):
        self.page_limit = page_limit
        self.columns = columns
        self.body_font_pt = body_font_pt
        self.min_figure_text_pt = min_figure_text_pt

    @classmethod
    def load(cls, path: Path) -> "Rules":
        data = yaml.safe_load(Path(path).read_text()) or {}

        known = set(vars(cls()))
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(
                f"unknown key(s) in {path}: {', '.join(unknown)}. "
                f"Valid keys are: {', '.join(sorted(known))}"
            )

        return cls(**data)


class Author:
    def __init__(self, name, affiliation=""):
        self.name = name
        self.affiliation = affiliation

    def __eq__(self, other):
        if not isinstance(other, Author):
            return NotImplemented
        return self.name == other.name and self.affiliation == other.affiliation


class Graphic:
    def __init__(self, index, start, end, options,
                 path, env="", env_begin=(0, 0), env_end=(0, 0), reason=""):
        self.index = index
        self.start = start
        self.end = end
        self.options = options
        self.path = path
        self.env = env
        self.env_begin = env_begin
        self.env_end = env_end
        self.reason = reason


class Measured:
    def __init__(self, index, page, x0, y0,
                 x1, y1, overflow=0.0, text_per_width=None, text_source=""):
        self.index = index
        self.page = page
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.overflow = overflow
        self.text_per_width = text_per_width
        self.text_source = text_source

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def text_pt(self) -> float | None:
        return None if self.text_per_width is None else self.text_per_width * self.width


class Geometry:
    def __init__(self, column, text, left, gap):
        self.column = column
        self.text = text
        self.left = left
        self.gap = gap

    def bounds(self, x0: float, double: bool) -> tuple[float, float]:
        if double or self.column >= self.text:
            return self.left, self.left + self.text
        if x0 < self.left + self.column:
            return self.left, self.left + self.column
        return self.left + self.column + self.gap, self.left + self.text


class FigureChange:
    def __init__(self, index, page, width_before, width_after, double_before,
                 double_after, overflow_before, text_before, text_after, note="", name=""):
        self.index = index
        self.page = page
        self.width_before = width_before
        self.width_after = width_after
        self.double_before = double_before
        self.double_after = double_after
        self.overflow_before = overflow_before
        self.text_before = text_before
        self.text_after = text_after
        self.note = note
        self.name = name


class FitReport:
    def __init__(self, changes, pages_before, pages_after, page_limit,
                 fitted_tex=None, pdf=None, summary="", policy="readable", min_pt=7.0):
        self.changes = changes
        self.pages_before = pages_before
        self.pages_after = pages_after
        self.page_limit = page_limit
        self.fitted_tex = fitted_tex
        self.pdf = pdf
        self.summary = summary
        self.policy = policy
        self.min_pt = min_pt

"""One open paper: its Manuscript, its folder, and everything you can do to it.

The window and the command line both go through this class, so they
cannot drift apart. Every edit is saved at once to manuscript.json in the
project folder, next to the paper.

    <paper>-prarup/
        manuscript.json   the paper as Prarup holds it, with your edits
        media/            every image, copied in
        paper.tex         the IEEE LaTeX, written on each build
        build/paper.pdf   the compiled paper
"""

import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pymupdf

from prarup import images as forensics
from prarup.analyze import Finding, analyze
from prarup.checks import UnreadablePdf, run_all_checks
from prarup.compile import compile_pdf
from prarup.figures import find_graphics, instrument
from prarup.measure import measure
from prarup.fit import FitFailed, describe, fit_paper
from prarup.ingest import open_paper
from prarup.manuscript import Block, Manuscript
from prarup.models import Author, Issue, Rules
from prarup.renderer import render


@dataclass
class BuildResult:
    pdf: Path | None
    issues: list = field(default_factory=list)   # PDF compliance issues
    log: str = ""
    pages: int = 0

    @property
    def ok(self) -> bool:
        return self.pdf is not None


class Project:
    def __init__(self, source: Path, folder: Path, manuscript: Manuscript):
        self.source = Path(source)
        self.folder = Path(folder)
        self.m = manuscript
        self.reports: list = []           # last image reports
        self.last_build: BuildResult | None = None

    # ------------------------------------------------------------ open, save

    @staticmethod
    def folder_for(source: Path) -> Path:
        return source.parent / f"{source.stem}-prarup"

    @classmethod
    def open(cls, source: Path, folder: Path | None = None, fresh: bool = False) -> "Project":
        """Open a paper, resuming saved edits unless the source changed since."""
        source = Path(source).resolve()
        folder = Path(folder) if folder else cls.folder_for(source)
        saved = folder / "manuscript.json"
        if saved.exists() and not fresh:
            m = Manuscript.load(saved)
            if m.source_mtime >= source.stat().st_mtime:
                return cls(source, folder, m)
        m = open_paper(source, folder)
        m.source_mtime = source.stat().st_mtime
        project = cls(source, folder, m)
        project.save()
        return project

    def save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        self.m.save(self.folder / "manuscript.json")

    # ------------------------------------------------------------ edits

    def _block(self, block_id: str) -> Block:
        block = self.m.find(block_id)
        if block is None:
            raise KeyError(f"no block {block_id}")
        return block

    def set_front(self, title: str | None = None, authors: list | None = None,
                  abstract: str | None = None, keywords: str | None = None) -> None:
        if title is not None:
            self.m.title = title
        if authors is not None:
            self.m.authors = [a if isinstance(a, Author) else Author(*a) for a in authors]
        if abstract is not None:
            self.m.abstract = abstract
        if keywords is not None:
            self.m.keywords = keywords
        self.save()

    def set_text(self, block_id: str, text: str) -> None:
        block = self._block(block_id)
        if block.text != text:
            block.text, block.edited = text, True
            self.save()

    def set_caption(self, block_id: str, caption: str) -> None:
        self._block(block_id).caption = caption
        self.save()

    def set_kind(self, block_id: str, kind: str, level: int = 1) -> None:
        """Re-tag a block: a paragraph that is really a heading, or the reverse."""
        block = self._block(block_id)
        if kind not in ("heading", "para", "quote"):
            raise ValueError("a block can be re-tagged as heading, para or quote")
        block.kind, block.level, block.edited, block.detected = kind, level, True, "re-tagged by you"
        self.save()

    def delete(self, block_id: str) -> None:
        self.m.blocks.remove(self._block(block_id))
        self.save()

    def move(self, block_id: str, step: int) -> None:
        blocks = self.m.blocks
        i = blocks.index(self._block(block_id))
        j = max(0, min(len(blocks) - 1, i + step))
        blocks.insert(j, blocks.pop(i))
        self.save()

    def _new_id(self) -> str:
        used = {int(b.id[1:]) for b in self.m.blocks if b.id[1:].isdigit()}
        return f"b{max(used, default=0) + 1}"

    def insert(self, after_id: str | None, kind: str, text: str = "") -> Block:
        """Add a paragraph, heading or empty figure after a block (or at the start)."""
        block = Block(id=self._new_id(), kind=kind, text=text, level=1 if kind == "heading" else 0,
                      edited=True, detected="added by you")
        at = 0 if after_id is None else self.m.blocks.index(self._block(after_id)) + 1
        self.m.blocks.insert(at, block)
        self.save()
        return block

    def _import_image(self, file: Path) -> str:
        media = self.folder / "media"
        media.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w.\-]", "_", Path(file).name)
        target, n = media / name, 1
        while target.exists() and target.read_bytes() != Path(file).read_bytes():
            target = media / f"{Path(name).stem}-{n}{Path(name).suffix}"
            n += 1
        if not target.exists():
            shutil.copy2(file, target)
        return f"media/{target.name}"

    def set_image(self, block_id: str, file: Path, index: int = 0) -> None:
        """Replace one image of a figure (or give a figure with none its image)."""
        block = self._block(block_id)
        path = self._import_image(file)
        if index < len(block.images):
            block.images[index] = path
        else:
            block.images.append(path)
        block.fit_width = ""                 # the old fitted width belonged to the old image
        self.save()

    def remove_image(self, block_id: str, index: int) -> None:
        block = self._block(block_id)
        del block.images[index]
        self.save()

    # ------------------------------------------------------------ checks

    def findings(self, classify: bool = False) -> list[Finding]:
        """Missing pieces and image problems, before any build."""
        self.reports = forensics.inspect(self.m, self.folder, classify=classify)
        return analyze(self.m, self.folder) + forensics.findings(self.reports)

    # ------------------------------------------------------------ build, fit

    def tex_path(self) -> Path:
        return self.folder / "paper.tex"

    def build(self, rules: Rules) -> BuildResult:
        """Write the IEEE LaTeX, compile it once with every figure marked,
        measure the figures, then strip the marks to leave a clean PDF."""
        latex = render(self.m, self.folder)
        tex = self.tex_path()
        tex.write_text(latex)
        marked = tex.with_name("paper-measure.tex")
        marked.write_text(instrument(latex))
        out = self.folder / "build"
        measured_pdf, log = compile_pdf(marked, out)
        if not measured_pdf.exists():
            self.last_build = BuildResult(None, [], _readable_error(log))
            return self.last_build
        graphics = find_graphics(latex)
        _, figures = measure(measured_pdf, graphics, self.folder)
        numbers = {img: n for n, fig in enumerate(self.m.figures(), start=1) for img in fig.images}
        names = {g.index: numbers.get(g.path) for g in graphics}
        pdf = out / "paper.pdf"
        _strip_marks(measured_pdf, pdf)
        try:
            issues = run_all_checks(pdf, rules) + _small_text(figures, rules, names)
        except UnreadablePdf as exc:
            issues = []
            log = str(exc)
        with pymupdf.open(pdf) as doc:
            pages = doc.page_count
        self.last_build = BuildResult(pdf, issues, log, pages)
        return self.last_build

    def fit(self, rules: Rules) -> list:
        """Fit the figures. Returns one report, or two when readable figures
        and the page limit conflict, for the user to choose between."""
        tex = self.tex_path()
        tex.write_text(render(self.m, self.folder))
        readable = fit_paper(tex, self.folder / "build", rules, "readable")
        options = [readable]
        if readable.pages_after > rules.page_limit:
            try:
                within = fit_paper(tex, self.folder / "build", rules, "limit")
                if within.pages_after < readable.pages_after:
                    options.append(within)
            except FitFailed:
                pass
        # the fitter counts every \includegraphics; name them as the paper does
        numbers = {img: n for n, fig in enumerate(self.m.figures(), start=1) for img in fig.images}
        paths = {g.index: g.path for g in find_graphics(tex.read_text())}
        for report in options:
            for change in report.changes:
                number = numbers.get(paths.get(change.index))
                change.name = f"Fig. {number}" if number else "Image in the text"
        return options

    def apply_fit(self, report) -> None:
        """Keep a fitted layout: each single-image figure remembers its width."""
        fitted = report.fitted_tex.read_text()
        for graphic in find_graphics(fitted):
            width = re.search(r"width=([^,\]]+)", graphic.options)
            for block in self.m.figures():
                if len(block.images) == 1 and block.images[0] == graphic.path and width:
                    block.fit_width = width.group(1).strip()
                    block.double = graphic.env == "figure*"
        self.save()

    # ------------------------------------------------------------ export

    def report_markdown(self, findings: list, issues: list) -> str:
        lines = [f"# Prarup report: {self.m.title or self.source.name}", "",
                 f"Source: `{self.source.name}` · {date.today().isoformat()}", ""]
        for title, items in [("Missing or wrong", [f for f in findings if f.group != "Images"]),
                             ("Images", [f for f in findings if f.group == "Images"]),
                             ("PDF compliance", issues)]:
            lines += [f"## {title}", ""]
            if not items:
                lines += ["All clear.", ""]
                continue
            for item in items:
                lines.append(f"- **{item.severity.upper()}** {item.code}: {item.message}")
            lines.append("")
        if self.reports:
            lines += ["## Figure images", "", "| Figure | File | Pixels | Printed dpi | AI evidence |",
                      "|---|---|---|---|---|"]
            for r in self.reports:
                lines.append(f"| {r.figure} | {Path(r.path).name} | {r.width_px}×{r.height_px} | "
                             f"{r.dpi:.0f} | {r.verdict} |")
            lines.append("")
        return "\n".join(lines)

    def export(self, destination: Path, rules: Rules) -> Path:
        """A submission archive: PDF, LaTeX source, images, bibliography, report."""
        result = self.build(rules)
        if not result.ok:
            raise RuntimeError("the paper does not compile, so there is nothing to export:\n"
                               + result.log)
        findings = self.findings()
        tex = self.tex_path().read_text()
        used = sorted(set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex)))
        destination = Path(destination)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(result.pdf, "paper.pdf")
            z.writestr("paper.tex", tex)
            for path in used:
                if (self.folder / path).is_file():
                    z.write(self.folder / path, path)
            if self.m.bibliography and (self.folder / self.m.bibliography).is_file():
                z.write(self.folder / self.m.bibliography, self.m.bibliography)
            z.writestr("prarup-report.md", self.report_markdown(findings, result.issues))
            z.writestr("README.txt",
                       "Built by Prarup with the IEEE conference template (IEEEtran).\n"
                       "Compile with XeLaTeX or Tectonic:  tectonic paper.tex\n"
                       "prarup-report.md lists what was checked and what is still open.\n")
        return destination


def _strip_marks(marked: Path, clean: Path) -> None:
    """Remove the invisible prarup:fig links used for measuring."""
    with pymupdf.open(marked) as doc:
        for page in doc:
            for link in page.get_links():
                if (link.get("uri") or "").startswith("prarup:fig:"):
                    page.delete_link(link)
        doc.save(clean, garbage=3, deflate=True)


def _small_text(figures: list, rules: Rules, names: dict) -> list:
    """GEOM-03: a figure whose text prints smaller than the readable minimum."""
    issues = []
    for m in figures:
        if m.text_pt is not None and m.text_pt < rules.min_figure_text_pt - 0.05:
            name = f"Fig. {names[m.index]}" if names.get(m.index) else "an image"
            issues.append(Issue(
                code="GEOM-03", severity="warning", can_fix=False,
                message=(f"{name} (page {m.page}) prints its text at {m.text_pt:.1f} pt; "
                         f"the minimum is {rules.min_figure_text_pt:g}. Use Fit figures"),
            ))
    return issues


def _readable_error(log: str) -> str:
    """The first LaTeX error in a compile log, in a form a person can act on."""
    lines = [l for l in log.splitlines() if l.startswith("error:") or l.startswith("!")]
    first = next((l for l in lines if "XeTeX engine" not in l and "something bad" not in l), "")
    where = re.search(r"paper\.tex:(\d+)", first)
    message = re.sub(r"^error:\s*(paper\.tex:\d+:\s*)?", "", first).strip()
    if not message:
        return log[-1500:] or "LaTeX did not produce a PDF."
    return f"LaTeX stopped at line {where.group(1)} of paper.tex: {message}" if where else message

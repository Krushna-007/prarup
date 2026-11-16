from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from prarup.analyze import Finding
from prarup.manuscript import Manuscript

Image.MAX_IMAGE_PIXELS = 200_000_000

COLUMN_INCHES = 3.5
MIN_DPI = 300


@dataclass
class ImageReport:
    path: str
    block_id: str
    figure: int
    width_px: int = 0
    height_px: int = 0
    printed_inches: float = 0.0
    dpi: float = 0.0
    duplicate_of: str = ""
    readable: bool = True
    error: str = ""


def dhash(image: Image.Image) -> int:
    small = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.get_flattened_data()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def _close(a: int, b: int) -> bool:
    return (a ^ b).bit_count() <= 4


def inspect_file(path: Path) -> tuple[ImageReport, int | None]:
    report = ImageReport(path=str(path), block_id="", figure=0)
    try:
        with Image.open(path) as image:
            report.width_px, report.height_px = image.size
            image.load()
            return report, dhash(image)
    except Exception as exc:
        report.readable = False
        report.error = str(exc)[:120]
        return report, None


def inspect(m: Manuscript, project: Path,
            printed: dict | None = None) -> list[ImageReport]:
    reports, hashes = [], []
    for number, fig in enumerate(m.figures(), start=1):
        share = COLUMN_INCHES * 0.98 / max(1, len(fig.images))
        for path in fig.images:
            file = project / path
            if not file.is_file():
                continue
            if file.suffix.lower() == ".pdf":
                continue
            report, h = inspect_file(file)
            report.path, report.block_id, report.figure = path, fig.id, number
            report.printed_inches = (printed or {}).get(path, share)
            if report.width_px and report.printed_inches:
                report.dpi = report.width_px / report.printed_inches
            if h is not None:
                twin = next((p for p, other in hashes if _close(h, other)), "")
                report.duplicate_of = twin
                hashes.append((path, h))
            reports.append(report)
    return reports


def findings(reports: list[ImageReport]) -> list[Finding]:
    out = []
    for r in reports:
        name = f"Fig. {r.figure} ({Path(r.path).name})"
        if r.dpi and r.dpi < MIN_DPI:
            out.append(Finding("IMG-01", "warning",
                               f"{name}: {r.dpi:.0f} dpi when printed {r.printed_inches:.1f} in wide "
                               f"({r.width_px} px); IEEE asks for at least {MIN_DPI}.", r.block_id, "Images"))
        if r.duplicate_of:
            out.append(Finding("IMG-05", "warning", f"{name} looks the same as "
                               f"{Path(r.duplicate_of).name}, used in another figure.", r.block_id, "Images"))
        if not r.readable:
            out.append(Finding("IMG-06", "warning", f"{name} could not be read: {r.error}",
                               r.block_id, "Images"))
    return out

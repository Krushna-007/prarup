import sys
from pathlib import Path

from prarup.process import find_tool, run_tool


class GhostscriptNotFound(Exception):
    pass


class RepairFailed(Exception):
    pass


KEEP_IMAGES = [
    "-dDownsampleColorImages=false",
    "-dDownsampleGrayImages=false",
    "-dDownsampleMonoImages=false",
    "-dAutoFilterColorImages=false",
    "-dAutoFilterGrayImages=false",
    "-dColorImageFilter=/FlateEncode",
    "-dGrayImageFilter=/FlateEncode",
    "-dPassThroughJPEGImages=true",
    "-dColorConversionStrategy=/LeaveColorUnchanged",
]


def find_ghostscript():
    for name in ("gs", "gswin64c", "gswin32c"):
        command = find_tool(name)
        if command:
            return command
    local = Path(sys.prefix) / "ghostscript" / "bin" / "gswin64c.exe"
    if sys.platform == "win32" and local.is_file():
        return str(local)
    return None


def embed_fonts(pdf_path: Path, out_path: Path) -> Path:
    ghostscript = find_ghostscript()
    if not ghostscript:
        raise GhostscriptNotFound("Ghostscript is not on PATH.")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = run_tool(
        [
            ghostscript,
            "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dQUIET",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-dEmbedAllFonts=true",
            "-dSubsetFonts=true",
            "-dMaxSubsetPct=100",
            *KEEP_IMAGES,
            f"-sOutputFile={out_path}",
            str(pdf_path),
        ],
        errors="replace",
    )

    if result.returncode != 0 or not out_path.exists():
        raise RepairFailed(result.stderr.strip() or "ghostscript produced no output")

    return out_path

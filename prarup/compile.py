from pathlib import Path

from prarup.process import find_tool, run_tool


class TectonicNotFound(Exception):
    pass


def compile_pdf(tex_path: Path, out_dir: Path) -> tuple[Path, str]:
    tectonic = find_tool("tectonic")
    if not tectonic:
        raise TectonicNotFound("tectonic is not installed or is missing from PATH.")

    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = out_dir / (tex_path.stem + ".pdf")
    pdf_path.unlink(missing_ok=True)

    result = run_tool(
        [tectonic, "--synctex", "--outdir", str(out_dir), str(tex_path)],
        errors="replace",
    )

    return pdf_path, result.stderr

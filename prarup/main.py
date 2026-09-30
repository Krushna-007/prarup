"""Command line entry point.

    prarup check paper.pdf           look at an existing PDF
    prarup build paper.tex           compile, then look at the result
    prarup build paper.docx          convert, compile, then look
"""

import argparse
import sys
from pathlib import Path

from prarup.checks import run_all_checks
from prarup.compile import TectonicNotFound, compile_pdf
from prarup.convert import (
    ConversionFailed,
    PandocNotFound,
    docx_to_tex,
    find_custom_macros,
)
from prarup.models import Rules

PRESETS = Path(__file__).parent / "presets"


def load_rules(args) -> Rules:
    """Rules come from a named preset, an explicit file, or the defaults."""
    if args.rules:
        return Rules.load(args.rules)
    preset = PRESETS / f"{args.preset}.yaml"
    if preset.exists():
        rules = Rules.load(preset)
    else:
        rules = Rules()
    if args.page_limit is not None:
        rules.page_limit = args.page_limit
    return rules


def prepare_tex(source: Path, out_dir: Path) -> Path:
    """Return a .tex path, converting from .docx first if needed."""
    if source.suffix.lower() != ".docx":
        return source

    tex_path = docx_to_tex(source, out_dir)
    macros = find_custom_macros(tex_path.read_text())
    if macros:
        print(
            "warning: custom macros may not have survived conversion: "
            + ", ".join(sorted(set(macros))),
            file=sys.stderr,
        )
    return tex_path


def print_report(issues, pdf_path: Path) -> None:
    """Print the findings in a form that reads top down."""
    if not issues:
        print(f"{pdf_path.name}: all checks passed.")
        return

    errors = sum(1 for i in issues if i.severity == "error")
    warnings = len(issues) - errors
    print(f"{pdf_path.name}: {errors} error(s), {warnings} warning(s)\n")

    for issue in issues:
        label = "ERROR" if issue.severity == "error" else "WARN "
        suffix = "   [can fix automatically]" if issue.can_fix else ""
        print(f"  {label}  {issue.code}  {issue.message}{suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prarup", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in [
        ("check", "check an existing PDF"),
        ("build", "convert and compile a manuscript, then check it"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("source", type=Path, help=".pdf, .tex or .docx")
        p.add_argument("--preset", default="ieee", help="preset name (default: ieee)")
        p.add_argument("--rules", type=Path, help="path to a rules YAML file")
        p.add_argument("--page-limit", type=int, help="override the page limit")
        if name == "build":
            p.add_argument("--outdir", type=Path, default=Path("build"))

    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        rules = load_rules(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.command == "check":
        pdf_path = args.source
    else:
        try:
            tex_path = prepare_tex(args.source, args.outdir)
            pdf_path, log = compile_pdf(tex_path, args.outdir)
        except (TectonicNotFound, PandocNotFound, ConversionFailed) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not pdf_path.exists():
            print("error: compilation failed\n", file=sys.stderr)
            print(log, file=sys.stderr)
            return 2

    if not pdf_path.exists():
        print(f"error: {pdf_path} does not exist", file=sys.stderr)
        return 2

    issues = run_all_checks(pdf_path, rules)
    print_report(issues, pdf_path)

    # non-zero when something would block submission, so this can gate a script
    return 1 if any(i.severity == "error" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())

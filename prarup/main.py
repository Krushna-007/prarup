import argparse
import sys
from pathlib import Path

from prarup.checks import UnreadablePdf, run_all_checks
from prarup.compile import TectonicNotFound
from prarup.fit import FitFailed, describe
from prarup.fix import GhostscriptNotFound, RepairFailed, embed_fonts
from prarup.ingest import OpenFailed
from prarup.models import Author, Rules
from prarup.pandoc import PandocFailed, PandocNotFound
from prarup.project import Project

PRESETS = Path(__file__).parent / "presets"
PAPERS = {".docx", ".tex", ".zip"}


def load_rules(args) -> Rules:
    if args.rules:
        rules = Rules.load(args.rules)
    else:
        preset = PRESETS / f"{args.preset}.yaml"
        rules = Rules.load(preset) if preset.exists() else Rules()
    if args.page_limit is not None:
        rules.page_limit = args.page_limit
    if getattr(args, "min_figure_text", None) is not None:
        rules.min_figure_text_pt = args.min_figure_text
    return rules


def parse_authors(values: list[str] | None) -> list[Author]:
    authors = []
    for value in values or []:
        name, _, affiliation = value.partition(":")
        authors.append(Author(name.strip(), affiliation.strip()))
    return authors


def print_report(issues, pdf_path: Path) -> None:
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


def print_findings(findings: list) -> None:
    for title, items in [("Missing or wrong", [f for f in findings if f.group != "Images"]),
                         ("Images", [f for f in findings if f.group == "Images"])]:
        print(f"{title}: {len(items) or 'nothing'}")
        for f in sorted(items, key=lambda f: f.severity != "error"):
            print(f"  {'ERROR' if f.severity == 'error' else 'WARN '}  {f.code}  {f.message}")
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prarup",
                                     description="Format and check research papers for submission.")
    sub = parser.add_subparsers(dest="command", required=True)
    commands = [
        ("inspect", "list what is missing and check every image"),
        ("build", "build the IEEE PDF and check it"),
        ("fit", "fit figures to their columns and the page limit, then build"),
        ("export", "write a submission zip"),
        ("check", "check an existing PDF"),
    ]
    for name, help_text in commands:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("source", type=Path, help=".docx, .tex, .zip, or .pdf for check")
        p.add_argument("--preset", default="ieee", help="preset name (default: ieee)")
        p.add_argument("--rules", type=Path, help="path to a rules YAML file")
        p.add_argument("--page-limit", type=int, help="override the page limit")
        if name in ("check", "build"):
            p.add_argument("--fix", action="store_true", help="repair fonts, then re-check")
        if name != "check":
            p.add_argument("--fresh", action="store_true",
                           help="read the paper again, dropping edits saved by the window")
            p.add_argument("--title", help="set the paper title")
            p.add_argument("--author", action="append", metavar="NAME:AFFILIATION",
                           help="set the authors (repeat for each)")
            p.add_argument("--abstract", help="set the abstract")
        if name == "fit":
            p.add_argument("--min-figure-text", type=float, metavar="PT",
                           help="smallest readable text inside a figure (default: preset)")
            p.add_argument("--policy", choices=["readable", "limit"], default="readable",
                           help="when readable figures break the page limit, which wins")
        if name == "export":
            p.add_argument("-o", "--output", type=Path, help="zip to write")
    return parser


def _check(pdf: Path, rules: Rules, fix: bool) -> int:
    try:
        issues = run_all_checks(pdf, rules)
    except UnreadablePdf as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if fix and any(i.can_fix for i in issues):
        fixed = pdf.with_name(pdf.stem + "-fixed.pdf")
        try:
            embed_fonts(pdf, fixed)
        except (GhostscriptNotFound, RepairFailed) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        issues = run_all_checks(fixed, rules)
        print(f"repaired -> {fixed}\n")
        pdf = fixed
    print_report(issues, pdf)
    return 1 if any(i.severity == "error" for i in issues) else 0


def main() -> int:
    args = build_parser().parse_args()
    try:
        rules = load_rules(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    source = args.source
    if not source.exists():
        print(f"error: {source} does not exist", file=sys.stderr)
        return 2
    suffix = source.suffix.lower()
    if args.command == "check" or (args.command == "build" and suffix == ".pdf"):
        return _check(source, rules, args.fix)
    if suffix == ".pdf":
        print(f"error: {args.command} needs the .docx, .tex or .zip the PDF was built from",
              file=sys.stderr)
        return 2
    if suffix not in PAPERS:
        print(f"error: {source.name} is not a .docx, .tex or .zip file", file=sys.stderr)
        return 2

    try:
        project = Project.open(source, fresh=args.fresh)
        if args.title or args.author or args.abstract:
            project.set_front(args.title, parse_authors(args.author) or None, args.abstract)

        if args.command == "inspect":
            findings = project.findings()
            print_findings(findings)
            for report in project.reports:
                print(f"  Fig. {report.figure}  {Path(report.path).name}: "
                      f"{report.width_px}x{report.height_px} px, {report.dpi:.0f} dpi")
            return 1 if any(f.severity == "error" for f in findings) else 0

        if args.command == "fit":
            options = project.fit(rules)
            chosen = next((o for o in options if o.policy == args.policy), options[0])
            if len(options) == 2:
                print("Readable figures and the page limit conflict; using the "
                      f"'{chosen.policy}' layout (--policy to choose).\n")
            print("\n".join(describe(chosen)) + "\n")
            project.apply_fit(chosen)

        if args.command == "export":
            out = args.output or source.with_name(source.stem + "-submission.zip")
            project.export(out, rules)
            print(f"exported -> {out}")
            return 0

        result = project.build(rules)
    except (TectonicNotFound, PandocNotFound, PandocFailed, OpenFailed, FitFailed,
            RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not result.ok:
        print(f"error: the paper did not compile.\n{result.log}", file=sys.stderr)
        return 2
    print_findings(project.findings())
    print(f"built -> {result.pdf} ({result.pages} pages)\n")
    if getattr(args, "fix", False):
        return _check(result.pdf, rules, True)
    print_report(result.issues, result.pdf)
    return 1 if any(i.severity == "error" for i in result.issues) else 0


if __name__ == "__main__":
    sys.exit(main())

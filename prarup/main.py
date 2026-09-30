"""Command line entry point.

    prarup check paper.pdf          look at an existing PDF
    prarup build  paper.tex         compile, then look at the result
"""

import argparse
import sys
from pathlib import Path

from prarup.checks import run_all_checks
from prarup.compile import TectonicNotFound, compile_pdf
from prarup.models import Rules


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


def main() -> int:
    parser = argparse.ArgumentParser(prog="prarup", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check an existing PDF")
    check.add_argument("pdf", type=Path)
    check.add_argument("--page-limit", type=int, default=6)

    build = sub.add_parser("build", help="compile a .tex file, then check it")
    build.add_argument("tex", type=Path)
    build.add_argument("--page-limit", type=int, default=6)
    build.add_argument("--outdir", type=Path, default=Path("build"))

    args = parser.parse_args()
    rules = Rules(page_limit=args.page_limit)

    if args.command == "check":
        pdf_path = args.pdf
    else:
        try:
            pdf_path, log = compile_pdf(args.tex, args.outdir)
        except TectonicNotFound as exc:
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

    # non-zero when something would block submission, so this can gate CI
    return 1 if any(i.severity == "error" for i in issues) else 0


if __name__ == "__main__":
    sys.exit(main())

"""Generate the PDFs the test suite runs against.

The interesting part is that the broken file and the fixed file come from
the same three lines of plotting code. Only the font type differs.

Run once from the project root:

    poetry run python tools/make_fixtures.py
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def make_figure(path: Path, fonttype: int) -> None:
    """Save a small plot using the given PDF font type."""
    matplotlib.rcParams["pdf.fonttype"] = fonttype
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.set_xlabel("time (s)")
    ax.set_ylabel("displacement (m)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def make_blank_pages(path: Path, count: int) -> None:
    """Save a PDF with the given number of empty pages."""
    import pymupdf

    doc = pymupdf.open()
    for _ in range(count):
        doc.new_page()
    doc.save(path)
    doc.close()


def make_protected(path: Path) -> None:
    """Save a PDF with an owner password set.

    Any encryption at all makes a file non-compliant, even when it can
    still be opened without a password.
    """
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner",
        permissions=pymupdf.PDF_PERM_PRINT,
    )
    doc.close()


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)

    # fonttype 3 is matplotlib's default and produces Type3 bitmap fonts,
    # which IEEE rejects even though they are embedded.
    make_figure(FIXTURES / "mpl_type3.pdf", 3)

    # fonttype 42 embeds TrueType outlines instead. This is the fix.
    make_figure(FIXTURES / "mpl_truetype.pdf", 42)

    # for the page-limit check: one at the limit, one over it
    make_blank_pages(FIXTURES / "six_pages.pdf", 6)
    make_blank_pages(FIXTURES / "eight_pages.pdf", 8)

    make_protected(FIXTURES / "protected.pdf")

    print(f"wrote fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()

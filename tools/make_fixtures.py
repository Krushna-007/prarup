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


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)

    # fonttype 3 is matplotlib's default and produces Type3 bitmap fonts,
    # which IEEE rejects even though they are embedded.
    make_figure(FIXTURES / "mpl_type3.pdf", 3)

    # fonttype 42 embeds TrueType outlines instead. This is the fix.
    make_figure(FIXTURES / "mpl_truetype.pdf", 42)

    print(f"wrote fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()

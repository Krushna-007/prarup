# 14 · How To Build It

The plan, written to be built by three people in four weeks using ordinary
Python. No metaclasses, no decorators you have to look up, no clever tricks.

If a piece of code here needs a paragraph of explanation, it is the wrong code.

---

## 1. The one idea worth keeping

Prarup is really one function:

```python
def check(pdf_path, rules):
    """Look at a compiled PDF and return a list of problems."""
```

Everything else either makes a PDF to hand to it, or shows what it gives back.

That leads to one rule, and it is the only architectural rule in the project:

> **`checks.py` never imports `subprocess`, `PySide6`, or anything that touches
> the outside world.**

Keep the checking code as plain functions over plain data. Then it is easy to
test, easy to read, and easy to explain in a viva. Everything messy (running
Tectonic, opening windows, calling an API) lives in other files.

---

## 2. Files

Flat. One file per job. You should be able to guess what is in each one.

```
prarup/
├── models.py      # Issue, Document, Rules   (dataclasses, no logic)
├── checks.py      # check_fonts, check_geometry, check_security   (pure)
├── compile.py     # runs Tectonic
├── convert.py     # .docx -> .tex using pandoc
├── fix.py         # runs Ghostscript to embed fonts
├── main.py        # command line entry point
├── gui.py         # the window
└── tests/
    ├── test_checks.py
    ├── test_models.py
    └── fixtures/
```

No `utils.py`, no `helpers.py`, no `common.py`. Those names attract every piece
of code nobody could place, and by week three they are unreadable.

Do not create folders until a file gets too big. A flat layout of nine files is
easier to navigate than three folders of three.

---

## 3. What the code actually looks like

### models.py

```python
from dataclasses import dataclass, field


@dataclass
class Issue:
    code: str            # "FONT-01"
    message: str         # "Helvetica is not embedded"
    severity: str        # "error" or "warning"
    can_fix: bool = False


@dataclass
class Rules:
    page_limit: int = 6
    columns: int = 2
    body_font_pt: float = 10.0


@dataclass
class Document:
    title: str = ""
    authors: list = field(default_factory=list)
    abstract: str = ""
    sections: list = field(default_factory=list)
    figures: list = field(default_factory=list)
```

Dataclasses only. They hold data, they do not do anything. `severity` is a plain
string because that is enough; swap it for an `Enum` later if you want, it is a
five minute change.

### checks.py

```python
import fitz                      # PyMuPDF
from models import Issue


def check_fonts(pdf_path):
    """Find fonts that IEEE PDF eXpress will reject."""
    issues = []
    doc = fitz.open(pdf_path)

    for page in doc:
        for font in page.get_fonts(full=True):
            ext = font[1]         # "n/a" means the font is not embedded
            font_type = font[2]   # "Type1", "TrueType", "Type3"
            name = font[3]

            if ext == "n/a":
                issues.append(Issue(
                    code="FONT-01",
                    message=f"{name} is not embedded",
                    severity="error",
                    can_fix=True,           # Ghostscript can embed it
                ))

            if font_type == "Type3":
                issues.append(Issue(
                    code="FONT-02",
                    message=f"{name} is a Type3 bitmap font",
                    severity="error",
                    can_fix=False,          # the figure must be remade
                ))

    doc.close()
    return issues


def check_page_count(pdf_path, rules):
    """Check the paper is not longer than the conference allows."""
    doc = fitz.open(pdf_path)
    pages = doc.page_count
    doc.close()

    if pages > rules.page_limit:
        over = pages - rules.page_limit
        return [Issue("GEOM-01", f"{over} page(s) over the limit", "warning")]
    return []
```

Plain functions. They take a path, they return a list. Nothing surprising.

### Running every check

No registry, no plugin system, no clever loop over classes:

```python
def run_all_checks(pdf_path, rules):
    issues = []
    issues += check_fonts(pdf_path)
    issues += check_page_count(pdf_path, rules)
    issues += check_security(pdf_path)
    return issues
```

Adding a check is one function and one line here. That is the whole extension
mechanism, and it is enough.

### compile.py

```python
import subprocess


def compile_pdf(tex_path, out_dir):
    """Run Tectonic. Return (pdf_path, log_text)."""
    result = subprocess.run(
        ["tectonic", "--synctex", "--outdir", str(out_dir), str(tex_path)],
        capture_output=True,
        text=True,
    )
    pdf_path = out_dir / (tex_path.stem + ".pdf")
    return pdf_path, result.stderr
```

`subprocess.run` for the command line version. Swap in `QProcess` only when you
reach the GUI and need it to not freeze. Do not start with `QProcess`.

### main.py

```python
import sys
from pathlib import Path
from models import Rules
from checks import run_all_checks
from compile import compile_pdf


def main():
    tex = Path(sys.argv[1])
    out = Path("build")
    out.mkdir(exist_ok=True)

    pdf, log = compile_pdf(tex, out)
    issues = run_all_checks(pdf, Rules())

    if not issues:
        print("All checks passed.")
        return

    for issue in issues:
        mark = "ERROR " if issue.severity == "error" else "WARN  "
        fixable = "  [can fix]" if issue.can_fix else ""
        print(f"{mark} {issue.code}  {issue.message}{fixable}")


if __name__ == "__main__":
    main()
```

That is the whole v0.1 program. Roughly 120 lines across four files, and it
already does the thing nobody else does.

---

## 4. Where classes belong

PC503 is a Python subject, so the object-oriented parts should be real, not
decoration. Use a class when something **has state**. Use a function when it does
not.

| Thing | Class or function? | Why |
|---|---|---|
| `Issue`, `Rules`, `Document` | dataclass | they hold data |
| `check_fonts` | function | path in, list out, no state |
| `TectonicRunner` | class | holds the process and the collected log |
| `MainWindow(QWidget)` | class | inherits from Qt, holds all the widgets |

The genuine inheritance in this project is `MainWindow(QWidget)` and friends.
That is worth showing in the report. Do not invent a class hierarchy just to have
one.

**If you later want a shared base class for checks**, the simple version is fine:

```python
class Check:
    code = ""
    def run(self, pdf_path, rules):
        raise NotImplementedError


class FontCheck(Check):
    code = "FONT-01"
    def run(self, pdf_path, rules):
        return check_fonts(pdf_path)
```

Only do this if you actually need it. With five checks, the `run_all_checks`
function above is clearer.

---

## 5. Writing it test first

### The rule

Write a test. Watch it fail. Write the smallest code that makes it pass. Then
tidy up. Repeat.

That is Uncle Bob's red, green, refactor. His three laws state it strictly: no
production code except to pass a failing test, no more test than is enough to
fail, no more code than is enough to pass. The step people skip is the third one,
tidying up, which is the whole reason you wrote the tests.

Do not aim for a one minute cycle at first. Five or ten minutes is fine while you
are learning it.

### Tests look like this

```python
# tests/test_checks.py
from pathlib import Path
from checks import check_fonts
from models import Rules

FIXTURES = Path(__file__).parent / "fixtures"


def test_clean_pdf_has_no_issues():
    assert check_fonts(FIXTURES / "clean.pdf") == []


def test_unembedded_font_is_reported():
    issues = check_fonts(FIXTURES / "unembedded.pdf")
    assert len(issues) == 1
    assert issues[0].code == "FONT-01"


def test_type3_font_is_reported():
    issues = check_fonts(FIXTURES / "mpl_type3.pdf")
    assert issues[0].code == "FONT-02"


def test_type3_cannot_be_auto_fixed():
    issues = check_fonts(FIXTURES / "mpl_type3.pdf")
    assert issues[0].can_fix is False


def test_fixed_figure_is_not_reported():
    """The corrected export must come back clean."""
    assert check_fonts(FIXTURES / "mpl_truetype.pdf") == []
```

Plain `assert`. No mocks, no fixtures beyond files, no setup classes.

That last test is the important one. A checker that flags everything is as
useless as one that flags nothing, and only a test on a *good* file catches it.

### The layering test

Instead of anything clever, just read the file:

```python
def test_checks_does_not_touch_the_outside_world():
    source = open("prarup/checks.py").read()
    assert "subprocess" not in source
    assert "PySide6" not in source
    assert "requests" not in source
```

Three lines, obvious to read, and it fails loudly the day someone breaks the one
architectural rule.

### Making the fixture files

The clever part is not the code, it is that you can generate the broken file and
the fixed file from the same script:

```python
# tools/make_fixtures.py
import matplotlib
import matplotlib.pyplot as plt


def make(path, fonttype):
    matplotlib.rcParams["pdf.fonttype"] = fonttype
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    ax.set_xlabel("time (s)")
    fig.savefig(path)
    plt.close(fig)


make("tests/fixtures/mpl_type3.pdf", 3)      # matplotlib's default: broken
make("tests/fixtures/mpl_truetype.pdf", 42)  # the fix
```

Run it once, commit the PDFs (they are a few KB), and the whole suite works on a
fresh clone.

---

## 6. Order of work

Each stage runs on its own and can be demonstrated.

| Stage | What works | Roughly |
|---|---|---|
| **v0.1** | `python main.py paper.tex` prints font problems | days 1 to 4 |
| **v0.2** | page count, security flags, `rules.yaml` | days 5 to 7 |
| **v0.3** | `.docx` input via pandoc | week 2 |
| **v0.4** | Qt window: open file, see PDF, see problems | week 2 to 3 |
| **v0.5** | Fix button (Ghostscript) | week 3 |
| **v0.6** | Export submission zip | week 4 |
| **v0.7** | LLM explanations, if time allows | week 4 |

**Build the command line version first.** It keeps the checking code free of Qt,
and it means you have something working in four days instead of three weeks. The
GUI then just calls functions that already work.

---

## 7. Style rules

Short list, easy to follow.

1. Functions do one thing and their name says what.
2. Type hints on function arguments if it helps reading. Not enforced, no mypy.
3. Docstring of one line on anything non-obvious. No essays.
4. No file longer than about 200 lines. Split it instead.
5. No inheritance unless Qt requires it or you have two real subclasses.
6. No abstraction until you have written the same thing twice.
7. If you cannot explain a piece of code in one sentence, rewrite it.

Rule 6 matters most. Earlier versions of these docs designed three abstract base
classes before a single line existed. Do not do that. Write the concrete thing,
and when you need a second one, then look at what they share.

---

**Previous:** [← 13 · Pitfalls](13-pitfalls.md) · **Home:** [README](../README.md)

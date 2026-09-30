# 14 · How To Build It

The design reduced to its smallest honest shape, and the order in which to write
it test-first.

This document revises two decisions made in
[05 · Python Design](05-python-design.md). Both revisions are noted where they
occur.

---

## 1. The design, reduced

Strip everything away and Prarup is one pure function:

```python
def check(pdf: Path, rules: Rules) -> list[Issue]: ...
```

No Qt. No subprocess. No network. Given a file and a rule set, it returns
findings.

Everything else is machinery that either produces a PDF to feed that function, or
presents what it returns. That is **functional core, imperative shell**: the core
holds the domain logic and stays pure, the shell owns every side effect, and the
core never calls the shell.

```
        ┌──────────────────────────────────────────┐
        │  SHELL  (impure, thin, hard to test)     │
        │  Qt widgets · QProcess · pypandoc        │
        │  file reads · Ghostscript · HTTP         │
        │                                          │
        │     ┌──────────────────────────────┐     │
        │     │  CORE  (pure, thick, easy)   │     │
        │     │  Document · Rules · Issue    │     │
        │     │  check() · geometry maths    │     │
        │     │  template rendering          │     │
        │     └──────────────────────────────┘     │
        └──────────────────────────────────────────┘
```

The core is where the tests live and where the value is. The shell should be
boring enough that a reading of it is sufficient review.

### What this buys us

Testing the core needs no fixtures beyond data, no mocks, no event loop, and no
network. Tests run in milliseconds, which is what makes a one-minute TDD cycle
possible at all.

---

## 2. Build order: the checker comes first

[07 · Scope and Timeline](07-scope-and-timeline.md) starts with the document
model. That is the wrong end. The checker depends on nothing (it takes a path and
returns findings), it is the flagship, and it is pure. So it is both the easiest
thing to build and the most valuable.

Build a **walking skeleton**: the thinnest slice that runs end to end, then
thicken it.

| Stage | Deliverable | Runs as |
|---|---|---|
| **v0.1** | Font check over a PDF | `prarup check paper.pdf` |
| **v0.2** | Compile a `.tex`, then check it | `prarup build paper.tex` |
| **v0.3** | Full rule set, `rules.yaml` | same CLI |
| **v0.4** | `.docx` ingestion | `prarup build paper.docx` |
| **v0.5** | Qt window wrapping the CLI behaviour | `prarup gui` |
| **v0.6** | Auto-fix | button in the report panel |
| **v0.7** | LLM explanations | optional panel |

Every stage is shippable and demonstrable on its own. v0.1 alone already
demonstrates the thing nobody else does.

**A CLI first, deliberately.** It forces the core to stay free of Qt, and it is
testable without an event loop. The GUI at v0.5 becomes a thin adapter over
functions that already work.

---

## 3. Test-driven development, applied

### The three laws

Robert Martin's rules, which are stricter than "write tests first":

1. Write no production code except to make a failing test pass.
2. Write no more of a test than is sufficient to fail. A compile or import error
   counts as a failure.
3. Write no more production code than is sufficient to pass the one failing test.

The cycle they produce is **red, green, refactor**, and it should take around a
minute. Martin's own warning is that the most common mistake is obeying the first
two laws and skipping the third. Green tests exist so that refactoring is safe;
if you never refactor, you paid for the tests and took none of the benefit.

### The first ten tests, in order

Write them exactly in this sequence. Each one should fail before you write any
implementation.

```python
# 1  the type exists and is inert
def test_issue_carries_a_message():
    assert Issue("x", Severity.ERROR).message == "x"

# 2  clean input produces nothing  (forces check() into existence)
def test_clean_pdf_has_no_font_issues():
    assert check_fonts(FIX / "clean.pdf") == []

# 3  the flagship  (forces real font-table reading)
def test_unembedded_font_is_flagged():
    issues = check_fonts(FIX / "unembedded.pdf")
    assert any("Helvetica" in i.message for i in issues)

# 4  the distinction that defines the product
def test_type3_font_is_flagged_separately():
    issues = check_fonts(FIX / "mpl_type3.pdf")
    assert any(i.code == "FONT-02" for i in issues)

# 5  and is honestly marked unfixable
def test_type3_is_not_auto_fixable():
    issue = next(i for i in check_fonts(FIX / "mpl_type3.pdf") if i.code == "FONT-02")
    assert issue.auto_fixable is False

# 6  the corrected figure must not be flagged  (guards against over-reporting)
def test_fonttype42_export_passes():
    assert check_fonts(FIX / "mpl_truetype.pdf") == []

# 7  severity ordering is real
def test_errors_sort_before_warnings():
    assert sorted([WARN, ERR])[0] is ERR

# 8  rules are data, not code
def test_rules_load_from_yaml(tmp_path):
    (tmp_path / "r.yaml").write_text("page_limit: 6\n")
    assert Rules.load(tmp_path / "r.yaml").page_limit == 6

# 9  geometry check reads the rule
def test_page_limit_breach_is_reported():
    assert any(i.code == "GEOM-01" for i in check_geometry(FIX / "seven_pages.pdf", Rules(page_limit=6)))

# 10 the registry composes  (forces the report function)
def test_report_runs_every_registered_check():
    assert {i.code for i in report(FIX / "mpl_type3.pdf", Rules())} >= {"FONT-02"}
```

Test 6 is the one people skip, and it is the one that matters. A checker that
flags everything is as useless as one that flags nothing, and only a negative
test catches that.

### Fixtures: generate them, do not commit blobs

The fixtures are the genuinely hard part of this project's tests. Generate them
with a script so the defect and its correction come from the same source:

```python
# tools/make_fixtures.py
import matplotlib as mpl, matplotlib.pyplot as plt

def figure(path, fonttype):
    mpl.rcParams["pdf.fonttype"] = fonttype
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1]); ax.set_xlabel("time (s)")
    fig.savefig(path); plt.close(fig)

figure("tests/fixtures/mpl_type3.pdf", 3)     # matplotlib's default: the bug
figure("tests/fixtures/mpl_truetype.pdf", 42) # the fix
```

Two lines of difference produce the failing case and the passing case. Run this
in `conftest.py` via a session fixture so a fresh clone is testable immediately.

---

## 4. Design rules we follow

Drawn from ArjanCodes and from the conventions already in use in your other
repositories.

### Protocol at boundaries, not ABC  *(revises doc 05)*

ABCs use **nominal** subtyping: a class is only compatible if it explicitly
inherits. Protocols use **structural** subtyping, the static equivalent of duck
typing, so any object with the right shape qualifies.

That difference matters most in tests. With a Protocol, a fake is three lines and
inherits nothing:

```python
class Reader(Protocol):
    def read(self, path: Path) -> Document: ...

class FakeReader:                       # note: no base class
    def read(self, path): return Document(title="t", sections=[])
```

Keep `ABC` only where a base class carries shared *implementation*. For the three
plug-in points (readers, checks, LLM backends) use `Protocol`.

### Build the abstraction on the second implementation  *(revises doc 05)*

Doc 05 designs three interfaces upfront. On day one there is one reader and one
check, so there is no interface to write. `Reader` appears when `.docx` arrives at
v0.4. Writing it earlier is guessing at a shape you have not met yet.

### Constructor injection

Pass dependencies in, never import them inside the class that uses them:

```python
class ComplianceReport:
    def __init__(self, checks: Sequence[Check]) -> None:
        self._checks = checks           # injected, therefore swappable in tests
```

### Data classes hold data, not behaviour

`Document`, `Issue`, `Rules`, `Figure` are `@dataclass(frozen=True)` where
possible. Behaviour lives in functions that take them and return new values.

### Honest file names

`fonts.py`, `geometry.py`, `bpp.py`. Never `utils.py`, `helpers.py`, or
`common.py`. A file whose name does not tell you what is in it will accumulate
everything nobody could place.

### Types are the specification

Full annotations, `mypy --strict` on `core/`. The shell may be looser.

---

## 5. Repository layout

```
prarup/
├── core/                    # pure. no Qt, no subprocess, no network.
│   ├── document.py          #   dataclasses
│   ├── rules.py             #   Rules.load()
│   ├── issue.py             #   Issue, Severity
│   ├── fonts.py             #   FONT-01, FONT-02
│   ├── geometry.py          #   GEOM-01
│   └── report.py            #   registry + composition
├── shell/                   # impure. thin.
│   ├── tectonic.py          #   QProcess wrapper
│   ├── pandoc.py            #   .docx
│   ├── ghostscript.py       #   auto-fix
│   └── llm/                 #   ollama.py, nim.py, null.py
├── ui/                      # Qt only. no logic.
├── cli.py                   # the v0.1-v0.4 entry point
├── tools/make_fixtures.py
└── tests/
    ├── core/                # fast, pure, the bulk of the suite
    └── shell/               # few, integration, marked slow
```

The rule that keeps this honest: **`core/` imports nothing from `shell/` or
`ui/`.** Enforce it with a test.

```python
def test_core_has_no_impure_imports():
    banned = {"PySide6", "subprocess", "requests", "pypandoc"}
    for py in (ROOT / "core").rglob("*.py"):
        tree = ast.parse(py.read_text())
        names = {n.name.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.Import) for n in node.names}
        assert not (names & banned), f"{py.name} imports {names & banned}"
```

That test is worth more than any amount of documentation about layering.

---

## 6. Definition of done, per stage

A stage is finished when all four hold:

1. Every new behaviour arrived via a failing test first.
2. `pytest` is green and `mypy --strict core/` is clean.
3. The stage runs end to end from the command line.
4. The refactor step actually happened: no duplication left that you can name.

---

## 7. What we deliberately do not build yet

| Not yet | Until |
|---|---|
| `Reader` Protocol | `.docx` arrives (v0.4) |
| LLM layer | the rules are complete (v0.7) |
| Qt interface | the CLI does the whole job (v0.5) |
| Preset generator | a second conference exists |
| PDF input | after v1.0, if at all |
| Plugin system | never, for a four-week project |

Each of these is a real feature. None of them is the flagship, and every one of
them can be added later without changing the core.

---

**Previous:** [← 13 · Pitfalls](13-pitfalls.md) · **Home:** [README](../README.md)

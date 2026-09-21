# 11 · Compliance Rules

The rule catalogue. For each check: how it is detected, whether it can be
repaired automatically, and — where it cannot — what the author has to do.

---

## The finding that shapes this whole module

There are **two different font failures**, they look identical to an author, and
they need completely different remedies.

| | Failure A | Failure B |
|---|---|---|
| **What** | Font referenced but not embedded | Font is **Type3** |
| **Cause** | Exporter assumed the font exists on the reader's machine | matplotlib's default `pdf.fonttype = 3` |
| **Why rejected** | Font unavailable on IEEE's archival system | Type3 is bitmap-based — **rejected even when correctly embedded** |
| **Auto-fixable?** | **Yes** — Ghostscript can embed it in place | **No** — the figure must be regenerated at source |

Ghostscript's own documentation is explicit: `-dEmbedAllFonts=true`
*"does not fix Type 3 fonts, and will not help if a font is entirely missing from
the system."*

So the auto-fix button is honest only if it distinguishes these two cases. A tool
that claims to "fix fonts" and silently fails on Type3 is worse than one that
says *"I cannot fix this, here is the two-line change to your plotting script."*

```
            ┌─────────────────────────┐
            │ page.get_fonts() entry  │
            └───────────┬─────────────┘
                        │
         ┌──────────────┴──────────────┐
         │                             │
   type == "Type3"              ext == "n/a"
         │                             │
   ✗ CANNOT AUTO-FIX            ✓ Ghostscript
   show the rcParams fix        embed in place
```

---

## The catalogue

### FONT-01 · Font referenced but not embedded ⭐

**Severity** Error · **Blocks submission** Yes · **Auto-fix** Yes

```python
for xref, ext, ftype, basefont, name, enc in page.get_fonts(full=True):
    if ext == "n/a":
        yield Issue(f"{basefont} is not embedded", auto_fixable=True)
```

We walk **every included figure**, not just the main document. This is the point
of the whole project: the `.tex` is clean, the figure is not.

**Repair**

```bash
gs -dNOPAUSE -dBATCH -dSAFER \
   -sDEVICE=pdfwrite \
   -dPDFSETTINGS=/prepress \
   -dEmbedAllFonts=true \
   -dSubsetFonts=true \
   -dMaxSubsetPct=100 \
   -sOutputFile=fixed.pdf  input.pdf
```

Re-run FONT-01 on the output. If it still fails, the font is missing from the
system entirely and no tool can recover it.

---

### FONT-02 · Type3 bitmap fonts

**Severity** Error · **Blocks submission** Yes · **Auto-fix** No

```python
if ftype == "Type3":
    yield Issue("Type3 bitmap font", auto_fixable=False, remedy=MPL_SNIPPET)
```

**Remedy shown to the author** — not applied automatically:

```python
import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42   # TrueType, not Type3
mpl.rcParams['ps.fonttype']  = 42
```

Both lines are needed. Setting only `pdf.fonttype` leaves EPS exports broken.

One caveat worth surfacing in the UI: Type42 produces a larger file, and
noticeably so for CJK glyph sets. That is the correct trade — IEEE rejects the
small one.

---

### PDFA-01 · PDF/A-1b conformance

**Severity** Error · **Blocks submission** Yes · **Auto-fix** Partial

Primary path — veraPDF, the reference implementation:

```bash
verapdf -f 1b --format json paper.pdf
```

Fallback when veraPDF is absent: check the XMP `pdfaid:part` / `pdfaid:conformance`
claim via pikepdf. **Report this as a weaker result.** A metadata claim is not
validation — a file can assert PDF/A-1b and fail it.

---

### DOC-01 · Security flags, bookmarks, crop marks

**Severity** Error · **Auto-fix** Yes

```python
pdf = pikepdf.open(path)
if pdf.is_encrypted:           yield Issue("encryption present")
if "/Perms" in pdf.Root:       yield Issue("permission flags set")
if "/Outlines" in pdf.Root:    yield Issue("bookmarks present")
```

Repair is a `pikepdf` round-trip that drops the offending dictionaries.

---

### GEOM-01 · Page count, margins, column width

**Severity** Warning · **Auto-fix** No

Measured on the rendered page, not on the source:

```python
page  = doc[i]
box   = page.rect
text  = page.get_text("dict")
left  = min(s["bbox"][0] for b in text["blocks"] for l in b.get("lines",[]) for s in l["spans"])
```

Compare against `rules.yaml`. Word count is not a substitute — a figure resize
moves the page boundary and no word count notices.

---

### STRUCT-01 · Caption placement

**Severity** Warning · **Auto-fix** Yes

IEEE convention: table captions above, figure captions below. Detected on the
`Document` model, before rendering, not on the PDF.

---

## Writing a new rule

Every check is one class and one registry line.

```python
class MyCheck(Check):
    name     = "MY-01"
    severity = Severity.WARNING

    def run(self, pdf: Path, rules: dict) -> list[Issue]:
        ...
```

```python
REGISTRY = [FontCheck, Type3Check, PdfaCheck, SecurityCheck, GeometryCheck, MyCheck]
report   = [i for c in REGISTRY for i in c().run(pdf, rules)]
```

No `if/elif` chain exists anywhere in `verify/`, and none should be added.

---

## Test fixtures

`tests/fixtures/` ships four PDFs that make these rules testable:

| File | Purpose |
|---|---|
| `clean.pdf` | All checks pass |
| `mpl_type3.pdf` | matplotlib default export — triggers FONT-02 |
| `mpl_fonttype42.pdf` | Same figure with the fix applied — must pass |
| `unembedded.pdf` | Font referenced only — triggers FONT-01, Ghostscript repairs it |

The pair `mpl_type3` / `mpl_fonttype42` is the important one: it proves both that
we detect the real failure and that we do not flag the corrected file.

---

**Previous:** [← 10 · Toolchain](10-toolchain.md) · **Next:** [12 · Implementation Notes →](12-implementation-notes.md)

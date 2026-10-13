# 11 · Compliance Rules

The rule catalogue. For each check: how it is detected, whether it can be
repaired automatically, and where it cannot, what the author has to do.

| Code | Rule | Severity | Auto-fix | Status |
|---|---|---|---|---|
| **FONT-01** | Font referenced but not embedded ⭐ | Error | Yes, Ghostscript | Built |
| **FONT-02** | Type3 bitmap font | Error | No, re-export the figure | Built |
| **GEOM-01** | Over the page limit | Warning | No | Built |
| **DOC-01** | Encryption or permission flags | Error | Yes, Ghostscript | Built |
| **DOC-02** | Bookmarks (PDF outline) | Warning | No | Built |
| PDFA-01 | PDF/A-1b conformance | n/a | n/a | Deferred, see below |
| GEOM-02 | Margins and column width | n/a | n/a | Not built |
| STRUCT-01 | Caption placement | n/a | n/a | Not built |

All of them live in `prarup/checks.py` as plain functions.

---

## The finding that shapes this whole module

There are **two different font failures**, they look identical to an author, and
they need completely different remedies.

| | Failure A | Failure B |
|---|---|---|
| **What** | Font referenced but not embedded | Font is **Type3** |
| **Cause** | Exporter assumed the font exists on the reader's machine | matplotlib's default `pdf.fonttype = 3` |
| **Why rejected** | Font unavailable on IEEE's archival system | Type3 is bitmap-based, **rejected even when correctly embedded** |
| **Auto-fixable?** | **Yes**, Ghostscript can embed it in place | **No**, the figure must be regenerated at source |

Ghostscript's own documentation is explicit: `-dEmbedAllFonts=true`
*"does not fix Type 3 fonts, and will not help if a font is entirely missing from
the system."*

**Measured, not assumed.** `tests/test_fix.py` runs Ghostscript over both fixtures
and asserts the outcome in each direction: the referenced font comes back
embedded, and the Type3 font comes back still Type3. Ghostscript exits zero in
both cases, which is why the exit code is never treated as evidence.

A further detail found only by running PyMuPDF against real files: **a Type3 font
also reports `ext == "n/a"`**, because its glyphs are inline procedures with no
external font file. Type3 is therefore matched first, or every Type3 font would
be reported twice and the author sent to a repair that cannot work.

### Tested on a real published paper

An IEEE Internet of Things Journal article (13 pages, 2026) was run through the
checker. Pages 9 to 12 hold matplotlib figures exported with the default
settings, and Prarup reported their fonts (`STIXGeneral-*`, matplotlib's maths
font, and Times New Roman) as **Type3**, which is exactly the failure this
project exists to catch. It also flagged the Helvetica in the "accepted for
publication" line that IEEE Xplore stamps on downloaded copies.

---

## How the report reads

Each problem font is reported **once**, with the pages it appears on. The
six-letter subset tag is dropped, so `FHXFSG+TimesNewRomanPSMT` reads as
`TimesNewRomanPSMT`:

```
ERROR  FONT-01  Helvetica is not embedded (pages 1-13)   [can fix automatically]
ERROR  FONT-02  STIXGeneral-Italic is a Type3 bitmap font (pages 9-12).
                Re-export the figure with matplotlib rcParams['pdf.fonttype'] = 42
WARN   GEOM-01  7 pages over the 6-page limit
```

Before this grouping, the same paper produced 55 lines.

---

## The catalogue

### FONT-01 · Font referenced but not embedded ⭐

**Severity** Error · **Auto-fix** Yes

```python
for font in page.get_fonts(full=True):
    if font[2] == "Type3":
        ...                       # FONT-02, checked first
    elif font[1] == "n/a":
        ...                       # FONT-01
```

Fonts inside an included figure appear on the page that draws the figure, so
checking the compiled PDF covers the figures as well as the text.

**Repair** (`prarup/fix.py`)

```bash
gs -dNOPAUSE -dBATCH -dSAFER -dQUIET -sDEVICE=pdfwrite \
   -dPDFSETTINGS=/prepress \
   -dEmbedAllFonts=true -dSubsetFonts=true -dMaxSubsetPct=100 \
   -dDownsampleColorImages=false -dDownsampleGrayImages=false \
   -dDownsampleMonoImages=false \
   -dAutoFilterColorImages=false -dAutoFilterGrayImages=false \
   -dColorImageFilter=/FlateEncode -dGrayImageFilter=/FlateEncode \
   -dPassThroughJPEGImages=true \
   -dColorConversionStrategy=/LeaveColorUnchanged \
   -sOutputFile=fixed.pdf input.pdf
```

Two things learned by testing:

- **`/prepress` is required.** Without it Ghostscript never embeds Helvetica and
  the other base-14 fonts, which are the ones figures most often leave out.
- **`/prepress` alone damages figures.** It downsamples images to 300 dpi and
  re-encodes lossless ones as JPEG. On the real paper above it shrank the file
  from 12.9 MB to 1.2 MB and changed up to 3.6% of a figure's pixels. The image
  flags after it switch that off; figures now render pixel-identical, and
  `tests/test_fix.py` checks this.

The repair writes `<name>-fixed.pdf`, never touches the original, and **re-runs
every check** on the output before reporting anything.

---

### FONT-02 · Type3 bitmap fonts

**Severity** Error · **Auto-fix** No

The message tells the author the fix:

```python
import matplotlib as mpl
mpl.rcParams['pdf.fonttype'] = 42   # TrueType, not Type3
mpl.rcParams['ps.fonttype']  = 42   # needed too for EPS exports
```

Type42 produces a larger file. That is the correct trade: IEEE rejects the small
one.

After a Ghostscript pass, Type3 fonts lose their names, so they are reported as
"an unnamed font". The original report, before repair, has the names.

---

### GEOM-01 · Page count

**Severity** Warning · **Auto-fix** No

Counted on the compiled PDF against `page_limit` in `presets/ieee.yaml` (6 for
IEEE conferences). A warning, because it is the author's call what to cut.

---

### DOC-01 · Encryption and permission flags

**Severity** Error · **Auto-fix** Yes

Read from PyMuPDF's `doc.metadata["encryption"]`, not `doc.is_encrypted`. The
latter only says whether the file is still locked, and it is already False for a
file that opens with an empty password, which is exactly the case to catch. The
Ghostscript repair writes an unencrypted copy, and the re-check confirms it.

---

### DOC-02 · Bookmarks

**Severity** Warning · **Auto-fix** No

`doc.get_toc()` is not empty. Usually left by `hyperref`. Some IEEE pipelines
reject bookmarks and others do not, hence a warning. Ghostscript keeps bookmarks,
so the message gives the remedy instead: load `hyperref` with
`[bookmarks=false]`, or drop it.

---

### Deferred: PDFA-01 · PDF/A-1b

Tectonic's output never claims PDF/A, so this check would flag every paper
Prarup builds, including clean ones. IEEE PDF eXpress for conferences focuses on
fonts, security and bookmarks. When added, it should use veraPDF
(`verapdf -f 1b --format json`) and say *"claimed, not validated"* when only the
XMP metadata is available.

### Not built: GEOM-02 margins, STRUCT-01 caption placement

Margins need measured values per conference and are prone to false positives
from page stamps such as the Xplore banner. Caption placement needs a parsed
document model rather than LaTeX text. Both are future work.

---

## Writing a new rule

1. Write a test in `tests/test_checks.py` against a small fixture PDF.
2. Write `check_something(pdf_path) -> list[Issue]` in `checks.py`. Open the PDF
   with `_open()`, so a bad file becomes `UnreadablePdf` and not a traceback.
3. Add one line to `run_all_checks`.

---

## Test fixtures

`tools/make_fixtures.py` generates them into `tests/fixtures/`:

| File | Purpose |
|---|---|
| `mpl_type3.pdf` | matplotlib default export, triggers FONT-02 |
| `mpl_truetype.pdf` | Same figure with `pdf.fonttype = 42`, must pass |
| `unembedded.pdf` | Helvetica referenced only, triggers FONT-01, Ghostscript repairs it |
| `protected.pdf` | Owner password set, triggers DOC-01 |
| `six_pages.pdf` / `eight_pages.pdf` | Either side of the page limit |
| `sample.docx` | A Word file with an image, for the full `.docx` → IEEE pipeline |

The pair `mpl_type3` / `mpl_truetype` is the important one: it proves both that
we detect the real failure and that we do not flag the corrected file. Bookmark
and image-quality fixtures are built inside their tests with `tmp_path`.

---

**Previous:** [← 10 · Toolchain](10-toolchain.md) · **Next:** [12 · Implementation Notes →](12-implementation-notes.md)

# 03 · Features

Features here are split honestly into two groups. The first group is what any
formatting tool must have to be taken seriously. The second group is why Prarup
is worth building.

---

## Table stakes

Necessary. Not interesting. Nobody will award marks for these alone.

| Feature | Notes | Status |
|---|---|---|
| Import `.tex` / `.docx` | `.docx` goes through pandoc into the IEEE template; `.tex` compiles as written | ✅ Built |
| Select target template | IEEE Conference for v1 | ✅ Built |
| Title, authors, abstract fields | A `.docx` carries none of these, so they are typed in the window | ✅ Built |
| Structured editor | Edit section text without touching LaTeX syntax | Not built |
| Live auto-compile | Debounced ~800 ms, background thread | Partly: background build on **Build** click |
| Embedded PDF preview | `QPdfView`, fit to width, multi-page | ✅ Built |
| Figure & table manager | Reorder, resize, replace, edit captions, insert new | Not built |
| Export | Compliant PDF + source bundle | Partly: repaired PDF is written; bundle zip not built |

---

## Differentiators

### ⭐ 1 · Pre-flight compliance check

**The flagship.** IEEE PDF eXpress is a gate at the end of the process. We move
that gate to the beginning, and we explain what it finds.

| Check | Implementation | Status |
|---|---|---|
| **Non-embedded fonts inside figures** | `page.get_fonts()` returns `"n/a"` for any font not embedded; figure fonts appear on the page that draws them | ✅ FONT-01, auto-fix |
| Type3 bitmap fonts | Font subtype via PyMuPDF; message gives the matplotlib fix | ✅ FONT-02 |
| Security flags | `doc.metadata["encryption"]` via PyMuPDF | ✅ DOC-01, auto-fix |
| Bookmarks | `doc.get_toc()` via PyMuPDF | ✅ DOC-02 |
| Page count | Actual rendered pages, against `presets/ieee.yaml` | ✅ GEOM-01 |
| PDF/A-1b conformance | veraPDF | Deferred |
| Margins & column width | Text bounding boxes against the page box | Not built |
| Caption placement | Tables above, figures below, IEEE convention | Not built |

Every result carries a **severity**, a **plain explanation** with the pages
involved, and where the fix is deterministic, a **one-click repair** that is
re-checked before it is reported.

Differentiators 2, 4 and 5 below are **designed, not built**. Offline (3) is true
today in the sense that matters: Prarup makes no network calls of its own. The
visible toggle is not built, and Tectonic's first compile on a new machine
downloads packages.

#### Why the figure-font check is the headline

It is the most common cause of IEEE rejection. It is invisible to the author.
No existing tool checks it before submission. And it costs about thirty lines of
PyMuPDF to detect.

The value here is not algorithmic difficulty — it is that nobody bothered.

---

### 2 · Page-budget optimiser

Not a word count. Measured on **rendered geometry**.

```
⚠  Over page limit by 0.4 pages

   Cheapest reductions, ranked by space saved per word removed:
     1. Fig. 3 → single column        −0.18 pp
     2. Tighten §4.2 (−40 words)      −0.11 pp
     3. Drop Table 2 footnote         −0.06 pp
```

Anyone who has fought a six-page limit at 2 a.m. understands this instantly.

---

### 3 · Offline mode

A visible toggle in the title bar. When enabled, no network call is made by any
component. Your unpublished manuscript stays on your machine.

This is not a privacy gesture. For researchers under embargo, or working on
patentable results, uploading a draft to a cloud service is simply not permitted.

---

### 4 · Preset generator

No template for your conference? Paste the call-for-papers text. The LLM reads the
prose requirements and emits a **draft `rules.yaml`** — which you then review and
edit.

```yaml
# generated draft — review before use
page_limit: 8
columns: 2
body_font_pt: 10
margins_mm: {top: 19, bottom: 25, left: 17, right: 17}
reference_style: ieee
figures: {caption_position: below}
```

The model writes the rules **once**. After that the rules run deterministically,
forever, with no model involved. This is the correct place for an LLM in this
system — and the only place we use one in the critical workflow.

---

### 5 · Submission bundle export

One archive containing everything a conference actually asks for:

```
paper_submission.zip
├── main.tex
├── IEEEtran.cls
├── refs.bib
├── figures/
└── compliance_report.pdf     ← proof it passes
```

---

## Feature comparison

| | Overleaf | SciSpace | PDF eXpress | **Prarup** |
|---|:-:|:-:|:-:|:-:|
| Template conversion | ✗ | ✓ | ✗ | ✓ (.docx → IEEE) |
| Live compile | ✓ | ✓ | ✗ | ✓ |
| Figure-font audit | ✗ | ✗ | partial | **✓** |
| Page-budget advice | ✗ | ✗ | ✗ | planned |
| Works offline | ✗ | ✗ | ✗ | **✓** |
| Template breadth | n/a | **40,000+** | n/a | 1 (v1) |

We lose on breadth. We win on everything that happens after the template is applied.

---

**Previous:** [← 02 · Architecture](02-architecture.md) · **Next:** [04 · UI Design →](04-ui-design.md)

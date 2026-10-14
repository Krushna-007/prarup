# 08 · Presentation Outline

**13 slides.** Product story first, one dedicated Python design slide.
Copy this content into the PPT template as-is.

> **If you run short on time, cut slide 4 or slide 11. Never cut slide 7.**

---

## Slide 1 — Title

> # प्रारूप · Prarup
> **An offline manuscript formatting and submission-compliance tool**
>
> PC503 — Python Programming
>
> Prateek Kalal · 202611009
> Om Patel · 202611030
> Krushna Parmar · 202611032

**Say:** "Prarup is the Hindi word for *format*. That is exactly what the tool does —
it fits your paper to the conference you are submitting to, then checks whether the
submission system will actually accept it."

---

## Slide 2 — The problem

**Papers get rejected before anyone reads them.**

- Every IEEE conference requires the PDF to pass **PDF eXpress** validation
- The most common failure is not in your `.tex` — it is **fonts inside your figures**
- Helvetica and Arial, silently referenced by **matplotlib, MATLAB, R** exports
- Also fatal: Type3 bitmap fonts · missing PDF/A-1b · security flags · bookmarks
- You find out **on deadline day**, from an error that explains nothing

**Say:** Ask the room how many have submitted to an IEEE conference. Whoever raises a
hand has lost an evening to this.

---

## Slide 3 — What Prarup does

```
  Your manuscript  →  Target format  →  Compiled PDF  →  Verified & ready
    .tex / .docx       IEEE Conf.       live preview     compliance report
```

1. **Convert** — restructure the manuscript into the target template
2. **Compile** — one click builds it and shows the PDF, locally, with Tectonic
3. **Verify** — check the output against the conference's real submission rules

**Say:** "Most tools stop at step two. Step three is the entire reason we are building this."

---

## Slide 4 — Why not use what exists?

| Tool | Converts | Live compile | **Compliance** | Offline |
|---|:-:|:-:|:-:|:-:|
| Overleaf | ✗ | ✓ | ✗ | ✗ |
| SciSpace / Typeset | ✓ | ✓ | ✗ | ✗ |
| IEEE PDF eXpress | ✗ | ✗ | ✓ *after submission* | ✗ |
| **Prarup** | ✓ | ✓ | **✓ before** | **✓** |

Two open gaps: **nothing checks compliance while you can still fix it**, and
**nothing runs on your own machine.**

**Say:** Be straight — SciSpace has 40,000+ templates and we will not beat that.
We beat them on verification and on privacy. Faculty respect an honest competitive slide.

---

## Slide 5 — System architecture

*Insert: architecture Mermaid diagram from [02 · Architecture](02-architecture.md)*

**Say:** Point at the dashed box. "The AI sits beside the pipeline, never inside it.
Next slide explains why."

---

## Slide 6 — Design decision: the LLM never touches your paper

**Rules check. The model only explains.**

| Deterministic — always runs | LLM — optional, advisory |
|---|---|
| Font embedding audit (built) | Explains a violation in plain English |
| Type3 detection (built) | Suggests cuts when over the limit |
| Page count, security, bookmarks (built) | Drafts a rule file from a new CFP |
| | *Never edits without confirmation* |

**Every check on the left is built and runs today with no AI at all.** The AI
column is the planned next step.

**Say:** "An LLM silently rewriting someone's unpublished paper is unacceptable.
The rules are mechanical and reproducible. The model is a translator, not an author."

---

## Slide 7 — ⭐ The figure-font trap

**Give this slide the most time. This is where the room understands the project.**

**Left — the problem**
```
your_paper.tex        ✓ clean
figure3.pdf           ← matplotlib export
  └─ Helvetica        ✗ NOT EMBEDDED
```
→ IEEE PDF eXpress: **REJECTED.** No explanation.

**Right — Prarup, real output on a published IEEE IoT Journal paper**
```
ERROR  FONT-01  Helvetica is not embedded (pages 1-13)   [can fix]
ERROR  FONT-02  STIXGeneral-Italic is a Type3 bitmap font (pages 9-12).
                Re-export the figure with matplotlib rcParams['pdf.fonttype'] = 42
```

Detected in **~30 lines of PyMuPDF**: `get_fonts()` returns `"n/a"` for any font
that is not embedded, and `"Type3"` for bitmap fonts. Fonts inside a figure are
listed on the page that draws it, so checking the compiled PDF covers figures.

The fix button embeds missing fonts with Ghostscript, **re-checks the result**,
and leaves figures pixel-identical. Type3 cannot be repaired by any tool, so
Prarup says so and gives the one-line change.

**Say:** "Most common reason IEEE bounces a paper. Completely invisible to the author.
No tool checks it before submission. And it is simple to detect — which is the point.
The value is not algorithmic difficulty. It is that nobody bothered."

---

## Slide 7b — ⭐ The figure fitter

**The second thing nobody checks: figures that no longer fit, or no longer read.**

| Build: the chart runs into the second column | Fit figures: across both columns, text 7.0 pt |
|---|---|
| `docs/images/window-overlap.png` | `docs/images/window-fitted.png` |

1. **Measure.** LaTeX reports the column widths; every graphic is wrapped in an
   invisible link, so its exact box comes back from the PDF. Text size inside
   the figure: from its own text if vector, **Tesseract OCR** if a bitmap
   (calibrated: within half a point).
2. **Decide.** Widest that fits the column. If that drops its text below 7 pt,
   span both columns instead.
3. **Page limit.** Shrink figures together by **binary search**, never below
   7 pt. If it still does not fit: *"about 0.4 pages over, cut text."*
4. **Verify.** Measure the result again. Never trust the arithmetic.

**Say:** "Shrinking a figure to fit is easy. Shrinking it without making it
unreadable is the hard part. The IEEE journal paper we tested prints its figure
labels at 2.4 pt. Prarup would not let that happen."

---

## Slide 8 — Interface

*Insert: `docs/images/window-clean.png` and `window-with-issue.png`*

**Say:** Walk one full loop out loud: open a .docx, type title and authors, Build,
see red, click Fix, see green. Then show the target mockup from
[04 · UI Design](04-ui-design.md) as where it is going.

---

## Slide 9 — Python design

*Insert: class diagram from [05 · Python Design](05-python-design.md)*

- **Dataclasses** for the data: `Issue`, `Rules`, `Author`, `Document`
- **Plain functions** for the checks: PDF in, list of issues out. Adding a rule
  is one function and one line
- **Real inheritance where Qt needs it:** `MainWindow(QWidget)`,
  `BuildWorker(QThread)` with signals
- **Custom exceptions** so every failure reaches the user as one sentence
- **One rule enforced by a test:** `checks.py` may not import `subprocess`,
  Qt or network code
- **160 pytest tests**, the window included, run headless

**Say:** "We designed three abstract base classes first, then deleted them when
the code showed they had one implementation each. No abstraction until you need
it twice."

---

## Slide 10 — Tech stack

| Layer | Tool |
|---|---|
| GUI | **PySide6** (`QPdfView`, `QThread`) |
| Templating | **Jinja2** → LaTeX |
| Compile | **Tectonic** |
| PDF inspection | **PyMuPDF** |
| DOCX import | **pandoc** |
| Font repair | **Ghostscript** |
| OCR (figure text size) | **Tesseract** |
| Packaging and tests | **Poetry**, **pytest**, **pytest-qt** |

**Why Tectonic:** no 5 GB TeX Live install. It fetches only what the document uses
and runs the right number of passes by itself.

**Logos:** one row, ~64 px, from [simpleicons.org](https://simpleicons.org) —
Python, Qt, LaTeX, Poetry. Greyscale except Python.

---

## Slide 11 — Scope

**Built**
✓ `.tex` + `.docx` in ✓ IEEE out ✓ PDF preview ✓ 6 compliance checks
✓ One-click repair, re-checked ✓ **Figure fitter** ✓ Title, authors, abstract read from Word
✓ Command line for scripts ✓ No AI needed

**Next**
Submission bundle export · auto-compile while typing · figure and caption
manager · LLM explanations (Ollama / NVIDIA NIM)

**Future scope**
PDF input (best open extractors reach ~83% on born-digital — deserves doing properly) ·
ACM, LNCS, Elsevier presets · auto-generated presets from a CFP · conversion diff

**Say:** "We would rather do one conference completely than four badly. Adding a
conference is a YAML preset and a template file."

---

## Slide 12 — Closing

> **Prarup checks your paper against the submission system's rules while you can
> still fix it — and does it without your manuscript leaving your machine.**

- One deterministic engine — verifiable, reproducible
- AI that assists and never overwrites
- Built entirely in Python

*Thank you. Questions?*

---

## Likely questions, and answers

**"Isn't this just Overleaf?"**
Overleaf compiles. It does not convert between templates and does not check
submission compliance. We do both, offline.

**"Why not just use SciSpace?"**
It is cloud-only and paid, and it does not verify the output. Our differentiator is
the compliance check, not the template library.

**"Can't ChatGPT do the formatting?"**
It can produce LaTeX. It cannot open a compiled PDF and read its font tables.
That is a measurement, not generation, and it is the part that decides
acceptance.

**"Why only one conference?"**
Because four half-working templates is a worse project than one that works. The
preset system is already general; breadth is a week of work, not a redesign.

**"What if the LLM gives wrong advice?"**
It never decides compliance. Every verdict comes from deterministic code. The model
would only rephrase a verdict the rules already produced, and it is not built yet.

**"Does the fix damage my paper?"**
No. It writes a separate `-fixed.pdf`, re-runs every check on it, and a test
confirms figures render pixel-identical before and after.

**"Is the fitter machine learning?"**
No, and it does not need to be. It is a measure-and-adjust loop: the
measurements are exact (LaTeX's own numbers, the PDF's own boxes) and the
search is a binary search. The only learned component is Tesseract's OCR, used
as a measuring instrument for text inside bitmaps.

**"Why 7 pt?"**
Our choice, set just under IEEE's 8 pt footnotes. It is one line in
`presets/ieee.yaml` and can be changed.

**"What about Type3 fonts?"**
No tool can convert them after the fact, Ghostscript included; we test that.
Prarup says so and gives the matplotlib setting to re-export the figure.

---

**Previous:** [← 07 · Scope & Timeline](07-scope-and-timeline.md) · **Next:** [09 · References →](09-references.md)

# 08 · Presentation Outline

**12 slides.** Product story first, one dedicated Python design slide.
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
2. **Compile** — live preview, auto-rebuild as you edit, like Overleaf but local
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
| Font embedding audit | Explains a violation in plain English |
| Page count, margins, columns | Suggests cuts when over the limit |
| Type3 / PDF-A detection | Drafts a rule file from a new CFP |
| Reference style validation | *Never edits without confirmation* |

**Disable the AI entirely and every compliance check still works.**

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

**Right — Prarup**
```
⛔  Fig. 3 — non-embedded font: Helvetica
    Source: figure3.pdf (matplotlib)
    Will be rejected by IEEE PDF eXpress
    → [ Fix automatically ]   [ Show me ]
```

Detected in **~30 lines of PyMuPDF** — `get_fonts()` returns `"n/a"` for any font
that is not embedded. We walk every included figure, not just the main document.

**Say:** "Most common reason IEEE bounces a paper. Completely invisible to the author.
No tool checks it before submission. And it is simple to detect — which is the point.
The value is not algorithmic difficulty. It is that nobody bothered."

---

## Slide 8 — Interface

*Insert: main-window mockup + click-path diagram from [04 · UI Design](04-ui-design.md)*

**Say:** Walk one full loop out loud — import, convert, see red, click fix, see green, export.
Five clicks.

---

## Slide 9 — Python design

*Insert: class diagram from [05 · Python Design](05-python-design.md)*

Three abstract base classes, three plug-in points:

- **`Reader`** — adding PDF later is one new subclass, nothing else changes
- **`Check`** — every rule is a class; the report is a list comprehension
- **`LLMBackend`** — `NullBackend` is why the offline claim is structurally true

Also: `@dataclass` for the model · `Enum` for severity · `QThread` for compile ·
`pytest` over fixture PDFs · type hints throughout.

**Say:** "`NullBackend` is not a placeholder. It is the default."

---

## Slide 10 — Tech stack

| Layer | Tool |
|---|---|
| GUI | **PySide6** |
| Templating | **Jinja2** → LaTeX |
| Compile | **Tectonic** |
| PDF inspection | **PyMuPDF**, **pikepdf** |
| DOCX import | **pypandoc** |
| Local AI | **Ollama** (Mac M4) |
| Cloud AI | **NVIDIA NIM** — free tier, no card |

**Why Tectonic:** no 5 GB TeX Live install. It fetches only what the document uses
and runs the right number of passes by itself.

**Logos:** one row, ~64 px, from [simpleicons.org](https://simpleicons.org) —
Python, Qt, LaTeX, NVIDIA, Ollama. Greyscale except Python and NVIDIA.

---

## Slide 11 — Scope

**In scope — 4 weeks**
✓ `.tex` + `.docx` in ✓ IEEE out ✓ Live compile
✓ Compliance checker ✓ Bundle export ✓ Works with AI off

**Future scope**
PDF input (best open extractors reach ~83% on born-digital — deserves doing properly) ·
ACM, LNCS, Elsevier presets · auto-generated presets from a CFP · conversion diff

**Say:** "We would rather do one conference completely than four badly. The architecture
already supports more — adding ACM is a preset file and a subclass."

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
It can produce LaTeX. It cannot inspect a compiled PDF's font tables, measure
rendered page geometry, or verify PDF/A conformance. Those are measurements, not
generation — and they are the part that decides acceptance.

**"Why only one conference?"**
Because four half-working templates is a worse project than one that works. The
preset system is already general; breadth is a week of work, not a redesign.

**"What if the LLM gives wrong advice?"**
It never decides compliance. Every verdict comes from deterministic code. The model
only rephrases a verdict the rules already produced.

---

**Previous:** [← 07 · Scope & Timeline](07-scope-and-timeline.md) · **Next:** [09 · References →](09-references.md)

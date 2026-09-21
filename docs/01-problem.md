# 01 · Problem & Motivation

## Papers get rejected before anyone reads them

Every IEEE conference requires that your PDF pass **IEEE PDF eXpress** validation
before it can be submitted. The service either accepts your file or rejects it.
When it rejects, the message is terse and the cause is rarely where you would look.

This is not a rare annoyance. It is the standard experience of submitting to an
IEEE venue, and it happens on the day of the deadline, when you have the least
time and the least patience.

---

## What actually fails

### The figure-font trap

The single most common PDF eXpress failure does not come from your `.tex` file.
It comes from the **figures you included**.

```
your_paper.tex           ✓  clean, compiles fine
  └── figure3.pdf        ←  exported from matplotlib
        └── Helvetica    ✗  referenced, not embedded
```

When matplotlib, MATLAB or R exports a vector figure, it frequently *references*
a font such as Helvetica, Times-Roman or Arial rather than embedding the glyph
outlines. Your PDF looks perfect on your machine — the font exists locally.
On IEEE's archival system it does not, so the file is non-compliant.

You cannot see this by looking at the PDF. Nothing in your LaTeX log mentions it.

### The rest of the list

| Failure | Why it matters |
|---|---|
| **Type3 bitmap fonts** | arXiv rejects these outright; outline fonts (Type1/TrueType) are required |
| **Not PDF/A-1b** | IEEE Xplore requires PDF/A-1b for long-term archival |
| **Security settings** | Any password or permission flag makes the file non-compliant |
| **Bookmarks / hyperlinks** | Forbidden in some conference pipelines |
| **Crop marks, date stamps** | Printer artefacts that survive into the final PDF |
| **Page limit overrun** | Measured on rendered geometry, not word count |

Every one of these is mechanically detectable. None of them is checked by the
tools researchers actually use while writing.

---

## Why existing tools don't solve it

| Tool | Converts format | Live compile | Checks compliance | Runs offline |
|---|:-:|:-:|:-:|:-:|
| Overleaf | ✗ | ✓ | ✗ | ✗ |
| SciSpace / Typeset | ✓ | ✓ | ✗ | ✗ |
| IEEE PDF eXpress | ✗ | ✗ | ✓ *(after submission)* | ✗ |
| **Prarup** | ✓ | ✓ | **✓ before submission** | **✓** |

**SciSpace is the incumbent.** It offers 40,000+ journal templates and one-click
formatting. We are not going to beat it on template breadth and we should not
pretend otherwise.

Two gaps remain open:

1. **Nothing verifies compliance while you can still act on it.** PDF eXpress is a
   gate, not a tool. It runs at the end, tells you pass or fail, and offers no guidance.
2. **Nothing runs locally.** Every cloud formatting service requires uploading an
   unpublished manuscript to a third party. For a lot of researchers that alone is
   disqualifying.

---

## Our position

> Prarup is not a better Overleaf. It is the missing step between *finished writing*
> and *successful submission*.

The conversion and the live preview are table stakes — necessary, unremarkable.
The **pre-flight compliance check** is the product.

---

## Who it is for

- Students submitting their first conference paper, who do not yet know PDF eXpress exists
- Researchers moving a rejected paper from one venue's template to another
- Anyone who cannot or will not upload unpublished work to a cloud service

---

**Next:** [02 · System Architecture →](02-architecture.md)

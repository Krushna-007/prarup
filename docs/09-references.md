# 09 · References

Every factual claim in these documents traces to one of these sources.
Cited so that anything on a slide can be defended if questioned.

---

## Submission compliance

- **IEEE PDF eXpress — common LaTeX errors and fixes.**
  Establishes that the most frequent failure originates in figures rather than the
  `.tex` source — non-embedded Helvetica, Times-Roman or Arial in PDF/EPS exports
  from MATLAB, R and matplotlib.
  <https://thelatexlab.com/blog/ieee-pdf-express-latex-errors-fixes/>

- **IEEE Xplore-compliant PDF guidelines.**
  PDF/A-1b archival requirement; prohibition on security settings, bookmarks, links
  and crop marks.
  <https://ewh.ieee.org/conf/edtm/2023/download/IEEEEDTM2023_IEEE_PDF_eXpress_Guideline_Final.pdf>

- **arXiv — submitting a PDF.**
  Type3 bitmap fonts rejected; outline (Type1/TrueType) fonts required; embedded
  JavaScript automatically rejected.
  <https://info.arxiv.org/help/submit_pdf.html>

---

## Competitive landscape

- **SciSpace / Typeset.io — journal templates.**
  40,000+ publisher templates, one-click formatting, cloud-only.
  <https://typeset.io/formats/>

---

## Document conversion

- **READoc: A Unified Benchmark for Realistic Document Structured Extraction.**
  Source of the accuracy figures used to justify deferring PDF input.
  <https://arxiv.org/pdf/2409.05137>

- **Open-source PDF-to-Markdown tool comparison (2026).**
  On born-digital PDFs: Marker 83.5, MinerU 83.3, Docling 64.0.
  <https://themenonlab.blog/blog/best-open-source-pdf-to-markdown-tools-2026>

- **Pandoc LaTeX ↔ DOCX limitations.**
  Custom macros break parsing; images are not auto-extracted; equation numbering
  needs `pandoc-crossref`.
  <https://hackmd.io/@wmvanvliet/rynY4IYXq>

---

## Tooling

- **Tectonic.** Self-contained TeX/LaTeX engine; automatic package fetching,
  automatic pass management, `--watch` mode.
  <https://github.com/tectonic-typesetting/tectonic>

- **PyMuPDF — font inspection.** `page.get_fonts()` returns `"n/a"` for any font
  that is not embedded. This single behaviour is the basis of our flagship check.
  <https://pymupdf.readthedocs.io/en/latest/font.html>

- **PySide6 QtPdf.** Native PDF viewer widget.
  <https://doc.qt.io/qtforpython-6/PySide6/QtPdf/index.html>

- **Paper-Linter.** Prior art for LaTeX source linting — typography, citations, spacing.
  <https://github.com/misc0110/Paper-Linter>

- **TeXtidote.** Spelling, grammar and style checking for LaTeX documents.
  <https://github.com/sylvainhalle/textidote>

- **PyQt6 LaTeX editor with live preview and SyncTeX.** Closest open-source
  reference implementation for our editor/preview coupling.
  <https://github.com/s-balli/latex-editor>

---

## Language models

- **NVIDIA NIM — free tier.** Free for NVIDIA Developer Program members, no credit
  card. Credit system abolished in early 2025; rate limits only (~40 RPM).
  <https://build.nvidia.com>

- **Ollama model sizing.** 3B–7B parameter models at Q4 quantisation run
  comfortably in 8 GB and support structured JSON output and tool calling.
  <https://www.morphllm.com/best-ollama-models>

---

## Licensing

- **LaTeX Project Public License (LPPL).** Permits redistribution of LaTeX class
  and package files, including IEEEtran. Springer LNCS and Elsevier terms must be
  verified individually before any future bundling.
  <https://www.ctan.org/license/lppl1>

---

**Previous:** [← 08 · Presentation Outline](08-presentation-outline.md) · **Home:** [README](../README.md)

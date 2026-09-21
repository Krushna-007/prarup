# 06 · Tech Stack

Everything is Python or invoked from Python. No web backend, no JavaScript, no server.

---

## The stack

| Layer | Choice | Why this one |
|---|---|---|
| **GUI** | PySide6 (Qt for Python) | `QPdfView`, `QSyntaxHighlighter`, `QFileSystemWatcher` and threading are all built in. Nothing else gives an Overleaf-style split view for free. LGPL. |
| **Templating** | Jinja2 → LaTeX | Real templating instead of string concatenation. Custom delimiters avoid clashing with LaTeX braces. |
| **Compile** | Tectonic | Self-contained; downloads only the packages the document uses; runs the correct number of passes automatically. |
| **PDF inspection** | PyMuPDF, pikepdf | `get_fonts()`, text bounding boxes, page geometry; pikepdf for document-level flags and PDF/A metadata. |
| **DOCX import** | pypandoc | Mature, handles OMML equations into real LaTeX math. |
| **Linting (optional)** | ChkTeX, TeXtidote | Shelled out, not reimplemented. |
| **Local AI** | Ollama | Runs on the Mac M4 via unified memory. Proves the offline claim. |
| **Cloud AI** | NVIDIA NIM | Free tier, no credit card, ~40 requests/min. Credits were abolished in early 2025 — rate limits only. |
| **Testing** | pytest | Focused on `verify/`. |
| **Packaging** | PyInstaller | Single-file build per platform. |

---

## Why Tectonic and not pdflatex

This choice does more work than it appears to.

| | TeX Live + latexmk | **Tectonic** |
|---|---|---|
| Install size | ~5 GB | ~30 MB binary |
| Missing package | Manual `tlmgr install` | Downloaded automatically |
| Number of passes | You guess, or use latexmk | Handled internally |
| Reproducibility | Depends on local install | Pinned bundle |

For a demo on three different machines, a user not needing a full TeX distribution
is the difference between the project working and the project not working.

---

## Why the AI split

Our three machines are not the same, so the design accommodates both:

| Machine | Backend | Role |
|---|---|---|
| **MacBook M4** | Ollama — Qwen2.5-7B / Gemma-3-4B at Q4 | Demonstrates true offline operation |
| **ASUS TUF F15, no usable GPU** | NVIDIA NIM | Day-to-day development, always fast |
| **Any machine, no network** | `NullBackend` | Full compliance checking, zero AI |

NIM is the practical default during development; Ollama on the Mac is what we show
when someone asks whether "offline" is real.

> **Note on GLM:** GLM-4.5 is a 355B-parameter mixture-of-experts model, and even
> GLM-4.5-Air is 106B. Neither runs on any machine we own. Small instruct-tuned
> models in the 4B–7B range at Q4 are what actually fit, and they are sufficient —
> our AI tasks are explanation and rule extraction, not reasoning.

---

## Dependency list

```txt
PySide6>=6.7
Jinja2>=3.1
PyMuPDF>=1.24
pikepdf>=9.0
pypandoc>=1.13
PyYAML>=6.0
requests>=2.32          # NVIDIA NIM
pytest>=8.0
```

External binaries: **Tectonic**, **Pandoc**, optionally **Ollama**.

---

## What we are not using, and why

| Not used | Reason |
|---|---|
| Streamlit / Gradio | Browser-based; cannot do tight editor↔PDF SyncTeX coupling |
| Tkinter | No usable PDF widget; we would spend the month fighting it |
| Electron / React | Not Python; the subject requires Python |
| Marker / MinerU | Excellent PDF extractors, but PDF input is out of v1 scope |
| A database | The document is a file. Nothing needs persistence beyond the project folder. |

---

**Previous:** [← 05 · Python Design](05-python-design.md) · **Next:** [07 · Scope & Timeline →](07-scope-and-timeline.md)

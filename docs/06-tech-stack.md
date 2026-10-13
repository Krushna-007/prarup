# 06 · Tech Stack

Everything is Python or invoked from Python. No web backend, no JavaScript, no server.

---

## The stack, as built

| Layer | Choice | Why this one |
|---|---|---|
| **GUI** | PySide6 (Qt for Python) | `QPdfView` gives a real PDF preview for free, and `QThread` keeps the window responsive during a build. LGPL. |
| **Templating** | Jinja2 → LaTeX | Real templating instead of string concatenation. Custom `\VAR{}` / `\BLOCK{}` delimiters avoid clashing with LaTeX braces. |
| **Compile** | Tectonic | Self-contained; downloads only the packages the document uses; runs the correct number of passes by itself. |
| **PDF inspection** | PyMuPDF | `page.get_fonts()` for the font checks, `doc.metadata` for encryption, `doc.get_toc()` for bookmarks, page count. One library covers every check we have. |
| **DOCX import** | pandoc, called with `subprocess` | Mature, and turns Word equations into real LaTeX math. Called directly, so there is no wrapper library to version. |
| **Font repair** | Ghostscript, called with `subprocess` | The standard tool for embedding referenced fonts. Its limits are documented in [11 · Compliance Rules](11-compliance-rules.md). |
| **Presets** | PyYAML | A conference's rules are a YAML file, so a new conference is data, not code. |
| **Testing** | pytest, pytest-qt | 105 tests, the window included, run headless. |
| **Packaging** | Poetry | One lock file, so all three machines install the same versions. |

Versions on the development Mac: PySide6 6.11, PyMuPDF 1.28, Jinja2 3.1,
PyYAML 6.0, Tectonic 0.17, pandoc 3.10, Ghostscript 10.08, Python 3.13.

**Python 3.11 to 3.13 only.** PySide6 publishes no wheels for 3.14 yet.

---

## Why Tectonic and not pdflatex

| | TeX Live + latexmk | **Tectonic** |
|---|---|---|
| Install size | ~5 GB | ~30 MB binary |
| Missing package | Manual `tlmgr install` | Downloaded automatically |
| Number of passes | You guess, or use latexmk | Handled internally |

For a demo on three different machines, a user not needing a full TeX
distribution is the difference between the project working and not working.

The first compile on a fresh machine needs the network to fetch packages. After
that it works offline. See [13 · Pitfalls](13-pitfalls.md).

---

## Planned for the LLM layer (not built yet)

| Machine | Backend | Role |
|---|---|---|
| **MacBook M4** | Ollama, a 4B to 7B model at Q4 | Shows that offline is real |
| **Laptops without a usable GPU** | NVIDIA NIM free tier | Day-to-day development |
| **Any machine** | none | Every compliance check runs with no model at all |

The model would only ever explain an `Issue`. It never decides compliance.

---

## Considered and dropped

These were in the proposal and turned out not to be needed.

| Dropped | Why |
|---|---|
| pikepdf | PyMuPDF already reports encryption and bookmarks. One PDF library is simpler. |
| pypandoc | A one-line `subprocess.run(["pandoc", ...])` does the same job with no extra dependency. |
| texoutparse | The window shows Tectonic's own error output, which already names the failing line. |
| PyInstaller | Run from source for the demo. Packaging is a stretch goal. |

## Not used, and why

| Not used | Reason |
|---|---|
| Streamlit / Gradio | Browser-based; no native PDF view |
| Tkinter | No usable PDF widget |
| Electron / React | Not Python; the subject requires Python |
| A database | The document is a file. Nothing needs persistence beyond the project folder. |

---

**Previous:** [← 05 · Python Design](05-python-design.md) · **Next:** [07 · Scope & Timeline →](07-scope-and-timeline.md)

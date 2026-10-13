# 12 · Implementation Notes

How the moving parts are actually wired. Written so that whoever picks up a
module does not have to rediscover these.

---

## The pipeline, in one function

`gui.build_paper` and `main.py` run the same sequence:

```
.docx ──pandoc──▶ body fragment ──document_from_latex──▶ Document
                                                           │
                                         render(doc, "ieee")
                                                           ▼
.tex ─────────────────────────────────────────────────▶ paper.tex
                                                           │
                                                  compile_pdf (Tectonic)
                                                           ▼
.pdf ─────────────────────────────────────────────────▶ paper.pdf
                                                           │
                                                   run_all_checks
                                                           ▼
                                                     list[Issue]
```

A `.tex` is compiled as it stands, because there is no reliable way to separate
an author's preamble from their body. A `.pdf` skips straight to the checks.

---

## Keeping the window responsive: QThread

```python
class BuildWorker(QThread):
    done = Signal(object, object)   # pdf_path, issues
    failed = Signal(str)

    def run(self):
        try:
            pdf_path, issues = build_paper(...)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(pdf_path, issues)
```

The whole pipeline (pandoc, Tectonic, checks) runs in the worker. Results come
back to the window through signals, which Qt delivers on the UI thread. Any
failure, including a compile error or an unreadable PDF, is shown in the
compliance list rather than swallowed.

The proposal planned `QProcess` for Tectonic alone. Running the whole pipeline
in one worker thread turned out simpler, because the pandoc step and the checks
need to be off the UI thread too.

**Not built yet:** auto-compile on typing (a debounced `QTimer`). The window has
no editor pane yet, so the user clicks **Build**.

---

## Never check a stale PDF

`compile_pdf` deletes the previous output before running Tectonic. Tectonic
writes nothing when compilation fails, and before this fix a broken edit was
reported as "all checks passed" against the last good build. The caller then
checks `pdf_path.exists()` and shows Tectonic's error output if it is missing.

---

## Reading fonts with PyMuPDF

```python
for number, page in enumerate(doc, start=1):
    for font in page.get_fonts(full=True):
        ext, ftype, name = font[1], font[2], font[3]
```

- `ext == "n/a"` → the font is **not embedded**
- `ftype == "Type3"` → bitmap font, rejected regardless of embedding, and also
  reports `"n/a"`, so test it first

`full=True` matters. Without it the tuple is shorter.

Fonts used by an included figure are listed on the page that draws it, so the
compiled PDF is enough; there is no need to open figure files separately.
Results are grouped per font with their page numbers, so a font used on every
page is one line.

All PDF opening goes through `checks._open`, which forces `filetype="pdf"` and
turns a missing or corrupt file into `UnreadablePdf` with a readable message.

---

## Asset handling in .docx conversion

pandoc emits `\includegraphics{media/rId9.png}` for every image whether or not
you ask for extraction. Without `--extract-media` it never writes the file that
reference points at, so the document compiles with the figures silently absent.

```bash
pandoc paper.docx -t latex --extract-media=. -o paper.tex     # run inside out_dir
```

- **`--extract-media=.`, not a directory name.** pandoc appends its own `media`
  folder to whatever you give it, so `--extract-media=media` writes
  `media/media/rId9.png` while the `.tex` refers to `media/rId9.png`.
- **`--standalone` only when compiling pandoc's output directly.** The build
  pipeline asks for a body fragment and wraps it in the IEEE template instead.

`tests/test_convert.py` checks that every `\includegraphics` path resolves.

---

## From a pandoc fragment to an IEEE paper

`document_from_latex` does three things, each covered by tests:

1. **Title.** A Word document usually has its own name as the only top-level
   heading, with the real sections under it. That heading becomes the title
   (unless one was typed in the window) and is removed from the body.
2. **Heading levels.** With the wrapper heading gone, every heading moves up one
   level, shallowest first, so `\subsubsection` lands one level up and not two.
3. **Figure placement.** Bare `\begin{figure}` gets `[htbp]`. Without it, IEEEtran
   may float a figure above the abstract.

Title, authors and abstract are typed in the window (or passed as `--title`,
`--author "Name:Affiliation"`, `--abstract`), because a `.docx` carries none of
them in a form pandoc exposes.

## pandoc defines its own macros

pandoc writes `tightlist`, `pandocbounded` and others. These are pandoc's, not
the author's, so `find_custom_macros` filters them before warning that the
author's own `\newcommand` definitions may not have survived conversion. The
template defines `\tightlist`, which IEEEtran lacks.

---

## Counting nothing twice

The compliance report runs on the **compiled PDF**, never on the source. The PDF
is what the conference receives, and source-level inspection cannot see what
the renderer did with a figure.

---

## Not built yet

- SyncTeX click-to-jump. Tectonic is already run with `--synctex`, so the
  `.synctex.gz` exists; the window does not use it yet.
- Parsing the LaTeX log into sentences. The raw Tectonic error output is shown.

---

**Previous:** [← 11 · Compliance Rules](11-compliance-rules.md) · **Next:** [13 · Pitfalls →](13-pitfalls.md)

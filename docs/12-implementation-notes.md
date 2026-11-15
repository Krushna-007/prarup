# 12 · Implementation Notes

How the moving parts are actually wired. Written so that whoever picks up a
module does not have to rediscover these.

---

## The pipeline

`Project` (in `project.py`) runs it, for the window and the command line alike:

```
.docx / .tex / .zip ──pandoc──▶ JSON tree ──ingest──▶ Manuscript (tagged blocks)
                                                          │   ▲
                                         analyze, images  │   │ edits from the window,
                                         (what is missing)│   │ saved to manuscript.json
                                                          ▼   │
                                              renderer ──▶ paper.tex (IEEE)
                                                          │
                              instrument + Tectonic, once ▼
                                         measure figures ──▶ strip marks ──▶ paper.pdf
                                                          │
                                         run_all_checks + figure text size
                                                          ▼
                                                    list[Issue]
```

Prarup no longer compiles an author's own LaTeX. It reads the paper into its
own structure and writes it again into the IEEE template, carrying over only
the author's safe maths packages and macros. That is what made real arXiv
papers written for pdfLaTeX compile (see doc 17).

---

## Keeping the window responsive: QThread

```python
class Worker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            result = self.job()          # any Project call: open, build, fit, export
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.done.emit(result)
```

Every slow job runs in a worker; the result comes back through a signal, which
Qt delivers on the UI thread. A failure is shown in a non-blocking message,
never swallowed.

**Auto-compile:** each edit restarts a 1.5 s single-shot `QTimer`; when it
fires, the paper is rebuilt in the background. An edit during a build sets a
flag, and the build runs again when the current one finishes.

**An editor must not emit `changed` while saving.** The window rebuilds the
editor on `changed`, which deletes the widget that was saving. Editors' `save()`
returns a message instead; only their Save buttons emit.

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

## Images in a .docx

pandoc names every Word image (`media/rId9.png`) but writes the file only when
asked to extract media. `pandoc.read` runs it inside the project folder with
`--extract-media=.`; pandoc appends its own `media` folder, so `=media` would
write `media/media/rId9.png`. `ingest._bring_media` and `_bring_inline_images`
then make sure every image a block uses is inside `media/`, and a missing one
becomes FIG-03 instead of a compile error.

`tests/test_ingest.py` checks that images are copied into the project and that
a missing one is reported.

---

## From the outline to an IEEE paper

`renderer.render` writes the Manuscript into `templates/ieee.tex.j2`:

1. **Title, authors, abstract, keywords** come from the front-matter fields,
   found by `ingest` and editable in the window. An empty abstract writes no
   heading at all.
2. **Figures** use the width and one/two-column choice saved by the fitter;
   a figure with no image prints a visible "image missing" box.
3. **Tables** are written as `tabular`/`tabularx`, spanning both columns when
   the text is too wide for one. pandoc's `longtable` is illegal in two columns.
4. **Equations**: an `align` nested inside `\[ \]` is unwrapped and its labels kept.
5. **Author LaTeX**: only safe maths packages and macros are carried over
   (`texsource.preamble_extras`), with `\newcommand` turned into
   `\providecommand` so a clash cannot stop the build. The template provides the
   commands pandoc writes (`\tightlist`, `\pandocbounded`, `\texorpdfstring`).

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

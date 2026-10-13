# 13 · Pitfalls

Things that will cost a day each if nobody writes them down first.

---

## Silent failures — the dangerous category

These produce a plausible-looking result while being wrong. They are worse than
crashes because nobody notices until the submission is rejected.

### The tool claims to fix a font and does not

Ghostscript's `-dEmbedAllFonts=true` returns exit code 0 on a Type3 font and
changes nothing. If the auto-fix does not re-run the check on its own output, it
will report success on a file that is still non-compliant.

**Rule: every auto-fix re-runs its own check and reports the post-fix state.**
No fix is reported as successful on the strength of an exit code.

### Figures disappear during .docx conversion

pandoc writes `\includegraphics` for every image but only writes the image files
with `--extract-media=.`. Without it the LaTeX compiles and the paper has no
figures. See [12 · Implementation Notes](12-implementation-notes.md).

**Rule: every `\includegraphics` path must resolve.** `tests/test_convert.py`
checks it.

### A failed compile is checked against the last good PDF

Tectonic writes nothing when compilation fails. If the previous PDF is still in
the build folder, the checks run on it and report "all checks passed". Fixed:
`compile_pdf` deletes the old output first, and a test covers it.

### The font repair quietly lowers figure quality

Ghostscript's `/prepress` setting, the usual advice for embedding fonts, also
downsamples images to 300 dpi and re-encodes lossless ones as JPEG. Fixed by
overriding the image settings; see [11 · Compliance Rules](11-compliance-rules.md).

### SyncTeX silently does nothing (for when click-to-jump is built)

Tectonic writes no `.synctex.gz` unless asked. We pass `--synctex`; without it
the feature would not error, clicks would just do nothing.

### A PDF/A claim is not PDF/A conformance

A file can carry `pdfaid:part=1` in its XMP and fail validation. If veraPDF is
unavailable, say *"claimed, not validated"* in the report rather than showing a
green tick.

---

## Environment traps

### Tectonic's first run is slow and needs the network

Tectonic downloads packages on demand. The first compile on a fresh machine
fetches a bundle and can take a minute; offline, it fails outright.

**Warm the cache before the demo.** Compile the fixture document once on each
machine the day before. Do not discover this in front of an audience.

This also interacts awkwardly with our own offline claim: *the app* works
offline, but *the first ever compile* needs the network. Say so plainly rather
than being caught by the question.

### The Tectonic bundle can move

Tectonic fetches packages from its default bundle, which can change between
releases. Keep the same Tectonic version on all three machines.

### Fonts differ across the three machines

A Mac has Menlo; a Windows laptop does not. If the UI or a generated document
names a font that is absent, the renderer substitutes silently and the layout
shifts. Restrict generated LaTeX to the fonts IEEEtran itself provides, and keep
UI fonts to a stack with real fallbacks.

---

## Design traps

### Do not let the LLM touch the document

Stated in [02 · Architecture](02-architecture.md) and repeated here because it is
the easiest rule to erode under deadline pressure. The first "just let it fix the
wording" commit is the one that ends the guarantee.

`checks.py` imports nothing that could call a model, and
`tests/test_layering.py` fails if it ever imports `subprocess`, Qt or a network
library. Keep it that way.

### Do not check the source when you mean the output

Source-level inspection cannot see what the renderer did. A `\includegraphics`
line tells you nothing about the fonts inside that figure. Checks run on the
compiled PDF.

### Do not measure page limits in words

A figure resize moves the page boundary; no word count notices. Measure rendered
geometry.

---

## Process traps

### Data and binaries first, code second

The single most common way a student project dies is waiting on something
external. Install Tectonic, Pandoc and Ghostscript on **all three machines in
week 1**, before writing the document model. A pipeline that cannot compile is
not testable.

### Test the rules, not the UI

`checks.py` is pure functions over fixture PDFs, trivially testable and the part
that actually matters. The window does have tests (pytest-qt, headless), but
they check wiring, not appearance.

### Keep a known-good fixture in version control

`tests/fixtures/six_pages.pdf` and `mpl_truetype.pdf` must always pass every
check. When something breaks, they tell you instantly whether the regression is
in the checker or in the document.

---

## Demo traps

| Trap | Prevention |
|---|---|
| Tectonic downloads a bundle mid-demo | Warm the cache the day before |
| The "broken" figure isn't actually broken | Run `prarup check tests/fixtures/unembedded.pdf` *before* presenting |
| A Type3 figure is shown with Fix | Fix cannot repair Type3. Use `unembedded.pdf` for the red-to-green flip |
| Live compile takes longer than expected | Pre-compile once so the Tectonic cache is hot |

The last one deserves emphasis. The red-to-green compliance flip is the moment
the project lands. Rehearse it on the actual machine, with the actual file.

---

**Previous:** [← 12 · Implementation Notes](12-implementation-notes.md) · **Home:** [README](../README.md)

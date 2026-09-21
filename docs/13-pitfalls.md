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

pandoc does not extract embedded media. The conversion succeeds, the LaTeX
compiles, and the paper has no figures. See [12 · Implementation Notes](12-implementation-notes.md).

**Rule: assert `len(doc.figures) > 0` when the source contained images**, and
surface a warning when the counts disagree.

### SyncTeX silently does nothing

`synctex = true` is off by default in `Tectonic.toml`. Without it the feature
does not error — clicks just do nothing, which reads as a UI bug for hours.

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

### Pin the Tectonic bundle

An unpinned `bundle` URL means the package set can move under you. A document
that built last week may stop building. Pin it in `Tectonic.toml` and treat a
bundle change as a deliberate commit.

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

`Check` has no reference to `LLMBackend`. Keep it that way — the type system is
the enforcement mechanism.

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

`verify/` is pure functions over fixture PDFs — trivially testable and the part
that actually matters. UI tests cost more than they return on a four-week
project.

### Keep a known-good fixture in version control

`tests/fixtures/clean.pdf` must always pass every check. When something breaks,
it tells you instantly whether the regression is in the checker or in the
document.

---

## Demo traps

| Trap | Prevention |
|---|---|
| Tectonic downloads a bundle mid-demo | Warm the cache the day before |
| Ollama model not pulled | `ollama pull qwen2.5:7b` in advance |
| NIM rate limit (~40 req/min) hit | Disable the AI panel for the demo; rules still run |
| The "broken" figure isn't actually broken | Verify `mpl_type3.pdf` fails the check *before* presenting |
| Live compile takes longer than expected | Pre-compile once so the Tectonic cache is hot |

The last one deserves emphasis. The red-to-green compliance flip is the moment
the project lands. Rehearse it on the actual machine, with the actual file.

---

**Previous:** [← 12 · Implementation Notes](12-implementation-notes.md) · **Home:** [README](../README.md)

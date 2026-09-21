# 10 · Toolchain

Every dependency, why it is there, and what breaks without it.

---

## Python packages

```txt
PySide6>=6.7          # GUI, QProcess, QPdfView, QSyntaxHighlighter
Jinja2>=3.1           # LaTeX templating  (see the delimiter warning below)
PyMuPDF>=1.24         # font tables, text bounding boxes, page geometry
pikepdf>=9.0          # document-level flags, encryption, metadata
pypandoc>=1.13        # .docx ingestion
PyYAML>=6.0           # rules.yaml
texoutparse>=0.1      # structured LaTeX log parsing
requests>=2.32        # NVIDIA NIM
pytest>=8.0           # tests
```

## External binaries

| Binary | Role | Required? |
|---|---|---|
| **tectonic** | LaTeX compilation | Yes |
| **pandoc** | `.docx` → LaTeX | Yes, for DOCX input |
| **gs** (Ghostscript) | Embedding referenced-but-missing fonts | Yes, for auto-fix |
| **verapdf** | PDF/A-1b validation | Optional — falls back to a metadata heuristic |
| **ollama** | Local LLM | Optional |

### Install (macOS)

```bash
brew install tectonic pandoc ghostscript
brew install --cask ollama          # optional
pip install -r requirements.txt
```

### Install (Windows)

Tectonic and Pandoc ship installers; Ghostscript is a separate download. Ship a
`tools/` directory check at startup and tell the user exactly which binary is
missing rather than failing inside a subprocess call.

---

## Tectonic: use the V2 interface

The V2 CLI is "cargo-like" — a `Tectonic.toml` defines the document and
`tectonic -X build` builds it.

```toml
# Tectonic.toml
[doc]
name    = "paper"
bundle  = "https://data.tectonic-typesetting.io/bundles/tlextras-2022.0r0/bundle.tar"

[[output]]
name    = "default"
type    = "pdf"
synctex = true          # <-- DEFAULTS TO FALSE. You must turn this on.
```

**Two flags that matter:**

- `synctex = true` — off by default. Without it there is no `.synctex.gz`, and
  click-to-jump between the editor and the PDF silently does nothing.
- `--keep-intermediates` — Tectonic keeps `.aux`, `.bbl` and friends **in memory**
  and never writes them to disk. Our verifier only needs the PDF, but the moment
  you want to debug a bibliography you will need this flag.

Pin the bundle URL. An unpinned bundle means a document that compiled last week
may not compile today.

---

## Jinja2: the delimiter trap

**Do not use Jinja2's defaults for LaTeX.** `{{ }}` and `{% %}` collide with
LaTeX's own braces, and the templates become unreadable and unparseable.

```python
latex_env = jinja2.Environment(
    block_start_string    = r'\BLOCK{',
    block_end_string      = '}',
    variable_start_string = r'\VAR{',
    variable_end_string   = '}',
    comment_start_string  = r'\#{',
    comment_end_string    = '}',
    line_statement_prefix = '%%',
    trim_blocks    = True,
    lstrip_blocks  = True,
    autoescape     = False,          # HTML escaping would corrupt LaTeX
    loader = jinja2.FileSystemLoader('presets/'),
)
```

A template then reads like real LaTeX:

```latex
\title{\VAR{doc.title}}
\BLOCK{for author in doc.authors}
  \author{\VAR{author.name}\thanks{\VAR{author.affiliation}}}
\BLOCK{endfor}
```

`autoescape=False` is deliberate. Jinja2's escaping is HTML-shaped and would
mangle every backslash in the output.

---

## What each library is actually for

**PyMuPDF** is the workhorse. `page.get_fonts()` returns tuples of
`(xref, ext, type, basefont, name, encoding)` — `ext` is `"n/a"` when the font is
not embedded, and `type` tells you `Type1` / `TrueType` / `Type3`. Those two
fields drive the entire flagship check.

**pikepdf** handles what PyMuPDF does not: encryption flags, document-level
permissions, outlines/bookmarks, and XMP metadata for the PDF/A claim.

**texoutparse** turns LaTeX's notoriously unstructured log into
`errors` / `warnings` / `badboxes` lists. LaTeX log parsing looks trivial and is
not; do not write your own.

**Ghostscript** is the only auto-fix we have for non-embedded fonts. Its limits
are important — see [11 · Compliance Rules](11-compliance-rules.md).

**veraPDF** is the reference PDF/A validator. It has no Python SDK; invoke it as
a subprocess and parse the JSON.

---

**Next:** [11 · Compliance Rules →](11-compliance-rules.md)

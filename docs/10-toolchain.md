# 10 · Toolchain

Every dependency, why it is there, and what breaks without it.

---

## Python packages

Managed by Poetry; the real list is `pyproject.toml`.

```toml
pymupdf  >= 1.28     # fonts, page count, encryption, bookmarks
pyyaml   >= 6.0      # presets/ieee.yaml
jinja2   >= 3.1      # LaTeX templating (see the delimiter warning below)
pyside6  >= 6.7      # the window, QPdfView, QThread

# dev only
pytest     >= 8.0
pytest-qt  >= 4.4    # drives the window in tests, headless
matplotlib >= 3.8    # only tools/make_fixtures.py uses it
```

## External binaries

| Binary | Role | Required? |
|---|---|---|
| **tectonic** | LaTeX compilation | Yes, for `build` |
| **pandoc** | `.docx` → LaTeX | Yes, for `.docx` input |
| **gs** (Ghostscript) | Embedding referenced-but-missing fonts | Yes, for `--fix` / the Fix button |

Each is looked up with `shutil.which` before use. If one is missing the user is
told which one and how to install it, rather than seeing a subprocess error.

### Install (macOS)

```bash
brew install tectonic pandoc ghostscript
poetry install
poetry run python tools/make_fixtures.py
poetry run pytest
```

### Install (Windows)

Tectonic and pandoc ship installers; Ghostscript is a separate download. Make
sure all three are on `PATH`.

---

## Tectonic: how we call it

```bash
tectonic --synctex --outdir build/ paper.tex
```

The plain V1 command line is enough: one `.tex` in, one PDF out. `--synctex` is
passed so a `.synctex.gz` exists if click-to-jump is added later.

Before compiling, `compile_pdf` **deletes the previous PDF** in the output
folder. Tectonic writes nothing when compilation fails, so a leftover file would
otherwise be checked as if it were the new one.

---

## Jinja2: the delimiter trap

**Do not use Jinja2's defaults for LaTeX.** `{{ }}` and `{% %}` collide with
LaTeX's own braces, and the templates become unreadable and unparseable.

```python
jinja2.Environment(
    block_start_string    = r'\BLOCK{',
    block_end_string      = '}',
    variable_start_string = r'\VAR{',
    variable_end_string   = '}',
    comment_start_string  = r'\#{',
    comment_end_string    = '}',
    trim_blocks    = True,
    lstrip_blocks  = True,
    autoescape     = False,          # HTML escaping would corrupt LaTeX
    keep_trailing_newline = True,
    loader = jinja2.FileSystemLoader(TEMPLATES),
)
```

A template then reads like real LaTeX (`prarup/templates/ieee.tex.j2`):

```latex
\title{\VAR{ doc.title }}
\BLOCK{ for author in doc.authors }
\IEEEauthorblockN{\VAR{ author.name }}
\IEEEauthorblockA{\VAR{ author.affiliation }}
\BLOCK{ endfor }
```

---

## What each tool is actually for

**PyMuPDF** is the workhorse. `page.get_fonts(full=True)` returns tuples of
`(xref, ext, type, basefont, name, encoding, ...)`. `ext` is `"n/a"` when the
font is not embedded, and `type` tells you `Type1` / `TrueType` / `Type3`. Those
two fields drive the flagship check. Fonts inside an included figure show up on
the page that draws it, so checking the compiled PDF covers the figures too.

**Ghostscript** is the only auto-fix we have for non-embedded fonts. Its limits
and the exact flags we pass are in [11 · Compliance Rules](11-compliance-rules.md).

---

**Next:** [11 · Compliance Rules →](11-compliance-rules.md)

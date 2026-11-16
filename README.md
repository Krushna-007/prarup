# Prarup

Prarup is a Tkinter app for preparing and checking research papers. It opens
Word manuscripts, LaTeX files, and zipped LaTeX projects. It builds an IEEE
conference PDF and reports missing captions, citation problems, font issues,
page limits, and image quality warnings.

Prateek Kalal, Om Patel, and Krushna Parmar developed Prarup for PC503.

## Run the app

Use Python 3.11 to 3.13 with Tkinter. From the project folder in PowerShell,
create the virtual environment if you need one, install the dependencies,
and start the app.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m prarup.ui.window
```

Install Pandoc to read manuscripts and Tectonic to build PDFs. Ghostscript
enables PDF repair. Tesseract is optional and measures text inside bitmap
figures. Prarup finds it on PATH or in `.venv/tesseract/` on Windows. The
Python libraries are PyMuPDF for PDFs, PyYAML for rules, Jinja2
for the LaTeX template, and Pillow for image checks.

## Try the demos

Open `demo/demo_word.docx` or `demo/demo_latex.tex`. Keep `demo_plot.png` beside
the LaTeX file. Click **Build PDF** to preview and check the paper, or **Fit figures**
to resize figures and review the result. Use **Fix PDF** for issues that can
be repaired automatically. **Export ZIP** saves the PDF, LaTeX, media, and report.

The demos include a figure with no caption. Select the figure and click
**Edit** to add one, then confirm that the caption warning clears.

## Project layout

| Folder | Contents |
|---|---|
| `prarup/` | Application code, Tkinter window, template, and rules |
| `demo/` | Word and LaTeX sample inputs |
| `tests/` | Tests and sample documents for them |
| `docs/` | Details on the [compliance rules](docs/compliance.md) and [figure fitting](docs/figure-fitting.md) |
| `submission/` | Course submission document |

Prarup saves edits and build outputs in a `<paper>-prarup/` folder next to
the source manuscript.

## Run tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:Path = "$(Resolve-Path .venv/Scripts);$env:Path"
.\.venv\Scripts\python.exe -m pytest tests
```

Tests that require an unavailable external program are skipped.
For the command line, run `.\.venv\Scripts\python.exe -m prarup.main --help`
from the project folder.

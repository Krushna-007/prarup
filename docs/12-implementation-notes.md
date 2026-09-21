# 12 · Implementation Notes

How the moving parts are actually wired. Written so that whoever picks up a
module in week 3 does not have to rediscover these.

---

## Compilation: QProcess, not QThread

Qt has a native answer for running an external program without freezing the UI,
and it is **not** threading.

```python
class TectonicRunner(QObject):
    finished = Signal(Path, list)          # pdf, log_lines

    def __init__(self):
        super().__init__()
        self.proc = QProcess()
        self.proc.readyReadStandardOutput.connect(self._stdout)
        self.proc.readyReadStandardError.connect(self._stderr)
        self.proc.finished.connect(self._done)
        self._log = []

    def build(self, workdir: Path):
        self.proc.setWorkingDirectory(str(workdir))
        self.proc.start("tectonic", ["-X", "build", "--keep-intermediates"])

    def _stdout(self):
        self._log += bytes(self.proc.readAllStandardOutput()).decode().splitlines()
```

`QProcess` starts the program and returns immediately; the event loop keeps
running and the editor stays live. Output arrives through
`readyReadStandardOutput` as the process writes it, so a progress indicator is
free.

Threads would work but bring manual lifecycle management for no benefit. Use the
Qt-native path.

### Debounce

Auto-compile fires on a `QTimer` restarted by every keystroke:

```python
self.debounce = QTimer(singleShot=True, interval=800)
self.debounce.timeout.connect(self.compile_now)
editor.textChanged.connect(self.debounce.start)     # restarts on each keystroke
```

Kill any in-flight compile before starting a new one, or two Tectonic processes
will race for the same output path.

---

## Parsing the LaTeX log

Do not write a regex for this. LaTeX logs are unstructured and every package
invents its own message shape.

```python
from texoutparse import LatexLogParser

parser = LatexLogParser()
with open(build_dir / "paper.log") as f:
    parser.process(f)

for err in parser.errors:      # also .warnings, .badboxes
    ui.add_error(str(err))
```

Surface the parsed message, and keep the raw log one click away. Authors who know
LaTeX will want it; everyone else never will.

---

## SyncTeX: click-to-jump both ways

Two prerequisites, both easy to miss:

1. `synctex = true` in `Tectonic.toml` — it is **off by default**
2. The `.synctex.gz` must sit beside the root file

**Forward** (editor line → PDF position):

```bash
synctex view -i LINE:COLUMN:main.tex -o paper.pdf
```

**Reverse** (PDF click → editor line):

```bash
synctex edit -o PAGE:X:Y:paper.pdf
```

Both print `key:value` lines; read `Page`, `x`, `y` for forward and `Input`,
`Line` for reverse. Wrap each in a tiny parser and keep the subprocess calls out
of the UI thread.

If `synctex` returns nothing, the usual cause is a stale `.synctex.gz` from a
compile that ran before the flag was enabled. Delete the build directory.

---

## Reading fonts with PyMuPDF

```python
doc = fitz.open(pdf_path)
for pno in range(doc.page_count):
    for xref, ext, ftype, basefont, name, enc in doc[pno].get_fonts(full=True):
        embedded = (ext != "n/a")
        ...
```

Two fields carry everything:

- `ext == "n/a"` → the font is **not embedded**
- `ftype == "Type3"` → bitmap font, rejected regardless of embedding

`full=True` matters. Without it the tuple is shorter and you lose the fields you
need.

To reach fonts *inside an included figure*, open the figure file directly — the
parent document reports the figure as an XObject, not as its constituent fonts.
Walk `Document.figures` from the model and open each asset path.

---

## The document model is the contract

Every reader returns `Document`. Every writer consumes `Document`. Nothing else
crosses that line.

```python
@dataclass
class Document:
    title:      str
    authors:    list[Author]
    abstract:   str
    sections:   list[Section]
    figures:    list[Figure]
    tables:     list[Table]
    references: list[Reference]
```

The practical test: adding PDF input later must touch exactly one new file in
`ingest/` and nothing else. If a change to a reader forces a change in `render/`,
the abstraction has leaked.

---

## Asset handling

`.docx` figures are **not** extracted automatically by pandoc. Pull them out
explicitly and rewrite the references:

```python
with zipfile.ZipFile(docx) as z:
    for n in z.namelist():
        if n.startswith("word/media/"):
            z.extract(n, assets_dir)
```

Then emit `\includegraphics{assets/image1.png}` in the LaTeX writer. A conversion
that silently drops figures is the most common way this pipeline appears to work
while producing a useless document.

---

## Custom macros break conversion

pandoc cannot resolve `\newcommand` definitions, so equations built from custom
macros fail to parse and vanish or corrupt.

Detect and warn rather than fail silently:

```python
CUSTOM = re.compile(r'\\(?:new|renew|provide)command\s*\{?\\(\w+)')
found  = CUSTOM.findall(source)
if found:
    warn(f"Custom macros may not survive conversion: {', '.join(found)}")
```

---

## Counting nothing twice

The compliance report runs on the **compiled PDF**, never on the source. That is
deliberate: the PDF is what the conference receives, and source-level inspection
cannot see what the renderer actually did with a figure.

The one exception is `STRUCT-01` (caption placement), which is a property of the
document model and is cheaper to check before rendering.

---

**Previous:** [← 11 · Compliance Rules](11-compliance-rules.md) · **Next:** [13 · Pitfalls →](13-pitfalls.md)

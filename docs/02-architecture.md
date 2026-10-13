# 02 · System Architecture

## Design principle

> **Rules check. The model only explains.**

Every compliance decision in Prarup is made by deterministic code — geometry,
font tables, page counts. The language model never decides whether something is
compliant and never edits the document on its own. It translates a machine
verdict into readable English and, when asked, suggests options.

Disable the AI entirely and every check still runs. That is not a fallback mode;
it is the default.

---

## Full system diagram

```mermaid
flowchart LR
    subgraph IN["INGEST"]
        A1[".tex"]
        A2[".docx"]
    end

    subgraph CORE["CORE ENGINE — deterministic"]
        B1["Document Model<br/>dataclasses"]
        B2["IEEE Preset<br/>rules.yaml + IEEEtran.cls"]
        B3["LaTeX Writer<br/>Jinja2"]
    end

    subgraph CMP["COMPILE"]
        C1["Tectonic"]
        C2["PDF"]
    end

    subgraph VER["PRE-FLIGHT CHECK"]
        D1["Font Audit"]
        D2["Geometry"]
        D3["PDF/A · Type3"]
        D4["Compliance Report"]
    end

    subgraph AI["ADVISORY — optional"]
        E1["Ollama · NVIDIA NIM"]
    end

    A1 --> B1
    A2 --> B1
    B1 --> B3
    B2 --> B3
    B3 --> C1 --> C2
    C2 --> D1 & D2 & D3
    D1 & D2 & D3 --> D4
    D4 -.->|explains| E1
    E1 -.->|plain English| D4
    D4 -->|fix & recompile| B1

    style VER fill:#fff4ed,stroke:#ff6b35
    style AI fill:#f7f7f7,stroke:#999,stroke-dasharray: 6 4
```

The dashed box is the point of the diagram. The AI sits **beside** the pipeline,
never inside it. It is not built yet, and every check already runs without it.

---

## The four stages

### 1 · Ingest

Two readers, one output type. Both produce the same `Document` object, so nothing
downstream needs to know where the manuscript came from.

| Input | Path | Fidelity |
|---|---|---|
| `.tex` | Compiled as written | Lossless. The author's own preamble is kept, since it cannot be reliably separated from the body |
| `.docx` | pandoc → LaTeX fragment → IEEE template | Good. Images extracted with `--extract-media=.`; custom macros are detected and warned about |

PDF input is deliberately **out of scope for v1**. See
[07 · Scope](07-scope-and-timeline.md) for the reasoning.

### 2 · Core engine

```mermaid
flowchart TD
    D["Document Model<br/>(single source of truth)"]
    R["rules.yaml<br/>page limit, margins,<br/>font sizes, ref style"]
    T["IEEEtran.cls"]
    J["Jinja2 template"]
    O["output.tex"]

    D --> J
    T --> J
    J --> O
    R -.->|used later by verifier| O
```

A preset is two things: a **LaTeX class file** (how it renders) and a
**`rules.yaml`** (what counts as compliant). Splitting them is what lets us add a
new conference without touching Python — and what lets the LLM generate a draft
preset from a call-for-papers.

### 3 · Compile

**Tectonic**, run inside a `QThread` worker so the window never blocks.

- Self-contained: downloads only the packages the document actually uses
- Runs the correct number of passes automatically — no `latexmk` guesswork
- Users do **not** need a 5 GB TeX Live installation

*Planned, not built:* auto-compile debounced at roughly 800 ms of keyboard idle.
Today the user clicks **Build**.

### 4 · Pre-flight check

```mermaid
flowchart TD
    PDF["compiled PDF"] --> F["FontCheck"]
    PDF --> G["GeometryCheck"]
    PDF --> P["PdfaCheck"]
    PDF --> S["SecurityCheck"]

    F --> R["Compliance Report<br/>severity-ranked"]
    G --> R
    P --> R
    S --> R

    R --> FIX["one-click fixes<br/>where deterministic"]
    R --> EXP["LLM explanation<br/>(optional)"]

    style R fill:#ff6b35,color:#fff
```

Each check is a plain function, `check_x(pdf_path) -> list[Issue]`, and
`run_all_checks` calls them in turn. Adding a new rule means one function and one
line. Built today: fonts, page count, security and bookmarks. PDF/A, margins and
caption placement are not built; see [11 · Compliance Rules](11-compliance-rules.md).

---

## Data flow, one full loop (as built; bundle export is not built yet)

```mermaid
sequenceDiagram
    actor U as User
    participant UI as PySide6 UI
    participant E as Engine
    participant T as Tectonic
    participant V as Verifier

    U->>UI: Import paper.docx
    UI->>E: read()
    E-->>UI: Document
    U->>UI: Target = IEEE Conference
    UI->>E: render(doc, preset)
    E->>T: compile output.tex
    T-->>UI: paper.pdf
    UI->>V: check(pdf, rules)
    V-->>UI: 1 error, 2 warnings
    U->>UI: Click "Fix what can be fixed"
    UI->>E: embed_fonts(paper.pdf)
    E-->>UI: paper-fixed.pdf
    UI->>V: check(paper-fixed.pdf)
    V-->>UI: all clear
```

---

## Module layout, as built

Flat, one file per job, as [14 · How To Build It](14-how-to-build.md) argues:

```
prarup/
├── models.py      Issue, Rules, Author, Document   (dataclasses)
├── checks.py      the compliance checks             (pure, no subprocess)
├── document.py    pandoc fragment → Document        (pure)
├── render.py      Document → IEEE LaTeX via Jinja2  (pure)
├── convert.py     .docx → LaTeX                     (runs pandoc)
├── compile.py     .tex → PDF                        (runs Tectonic)
├── fix.py         embed fonts                       (runs Ghostscript)
├── main.py        command line
├── gui.py         the window
├── presets/ieee.yaml
└── templates/ieee.tex.j2
tests/             105 tests, fixtures in tests/fixtures/
```

The proposal's nested packages (`ingest/`, `verify/`, `llm/` …) were never needed
at this size. `checks.py` is the spine: a test fails if it ever imports
`subprocess`, Qt or a network library.

---

**Previous:** [← 01 · Problem](01-problem.md) · **Next:** [03 · Features →](03-features.md)

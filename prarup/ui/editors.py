from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from prarup import pandoc
from prarup.models import Author
from prarup.ui.style import entry, text_box

IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg *.pdf")]


class Editor(ttk.Frame):

    def __init__(self, parent, window, key, heading, problems):
        super().__init__(parent, padding=12)
        self.window, self.project, self.key = window, window.project, key
        ttk.Label(self, text=heading, style="Title.TLabel").pack(anchor="w", pady=(0, 6))
        for f in problems:
            sign = "⛔ " if f.severity == "error" else "⚠ "
            ttk.Label(self, text=sign + f.message, style="Problem.TLabel",
                      wraplength=560).pack(fill="x", pady=(0, 4))

    def label(self, text, hint=False):
        ttk.Label(self, text=text, style="Hint.TLabel" if hint else "TLabel",
                  wraplength=560).pack(anchor="w", pady=(6, 2))

    def block_buttons(self):
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(10, 0))
        w = self.window
        for text, command in [("Save", w.save_editor), ("↑", lambda: w.move(-1)),
                              ("↓", lambda: w.move(1)), ("+ Paragraph", lambda: w.insert("para")),
                              ("+ Figure", lambda: w.insert("figure"))]:
            ttk.Button(row, text=text, command=command, width=len(text) + 2).pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Delete", style="Danger.TButton", width=8,
                   command=w.delete_block).pack(side="right")

    def save(self) -> str:
        return ""


class FrontEditor(Editor):

    def __init__(self, parent, window, key, problems):
        super().__init__(parent, window, key, "Title, authors, abstract", problems)
        m = self.project.m
        self.label("Found in the paper. Correct anything wrong; this is what goes in the IEEE title block.",
                   hint=True)
        self.label("Title")
        self.title = entry(self, m.title)
        self.title.pack(fill="x")
        self.label("Authors, one per line:  Name | Affiliation")
        self.authors = text_box(self, "\n".join(f"{a.name} | {a.affiliation}" for a in m.authors), 3)
        self.authors.pack(fill="x")
        self.label("Abstract")
        self.abstract = text_box(self, m.abstract, 6)
        self.abstract.pack(fill="x")
        self.label("Keywords (Index Terms)")
        self.keywords = entry(self, m.keywords)
        self.keywords.pack(fill="x")
        ttk.Button(self, text="Save", command=window.save_editor).pack(anchor="w", pady=(10, 0))
        {"title": self.title, "authors": self.authors, "abstract": self.abstract,
         "keywords": self.keywords}[key].focus_set()

    def save(self) -> str:
        authors = []
        for line in self.authors.get("1.0", "end").splitlines():
            name, _, place = line.partition("|")
            if name.strip():
                authors.append(Author(name.strip(), place.strip()))
        new = (self.title.get().strip(), authors, self.abstract.get("1.0", "end").strip(),
               self.keywords.get().strip())
        m = self.project.m
        if new == (m.title, m.authors, m.abstract, m.keywords):
            return ""
        self.project.set_front(*new)
        return "Title block saved."


class TextEditor(Editor):

    NAMES = {"para": "Paragraph", "heading": "Heading", "quote": "Quote", "list": "List",
             "equation": "Equation (LaTeX, without $ signs)", "code": "Code", "raw": "Raw LaTeX"}

    def __init__(self, parent, window, block, problems):
        super().__init__(parent, window, block.id, self.NAMES.get(block.kind, block.kind), problems)
        self.block = block
        if block.detected:
            self.label(f"Detected: {block.detected}", hint=True)
        self.kind = None
        if block.kind in ("para", "heading", "quote"):
            row = ttk.Frame(self)
            row.pack(anchor="w")
            ttk.Label(row, text="This block is a ").pack(side="left")
            self.kind = ttk.Combobox(row, values=["para", "heading", "quote"], state="readonly", width=10)
            self.kind.set(block.kind)
            self.kind.pack(side="left")
        self.text = text_box(self, block.text, 12)
        self.text.pack(fill="both", expand=True, pady=(6, 0))
        if block.kind != "equation":
            self.label("Markdown: *italic*, **bold**, $x^2$ for maths, [@key] to cite.", hint=True)
        self.block_buttons()

    def save(self) -> str:
        changed = False
        if self.kind and self.kind.get() != self.block.kind:
            self.project.set_kind(self.key, self.kind.get())
            changed = True
        text = self.text.get("1.0", "end-1c")
        if text != self.block.text:
            self.project.set_text(self.key, text)
            changed = True
        return "Saved." if changed else ""


class FigureEditor(Editor):

    def __init__(self, parent, window, block, problems, number, reports):
        super().__init__(parent, window, block.id, f"Figure {number}", problems)
        self.block = block
        self.pictures = []
        if block.detected:
            self.label(f"Detected: {block.detected}", hint=True)
        cards = ttk.Frame(self)
        cards.pack(fill="x")
        by_path = {r.path: r for r in reports}
        for index, path in enumerate(block.images):
            self.card(cards, index, path, by_path.get(path))
        if not block.images:
            self.label("No image. Add one below.", hint=True)
        ttk.Button(self, text="+ Add image…", command=lambda: self.choose(len(block.images))
                   ).pack(anchor="w", pady=(6, 0))
        self.label("Caption (IEEE adds \"Fig. N.\" itself)")
        self.caption = text_box(self, block.caption, 3)
        self.caption.pack(fill="x")
        if block.fit_width:
            self.label(f"Width set by Fit figures: {block.fit_width}"
                       + (", across both columns" if block.double else ""), hint=True)
        self.block_buttons()

    def card(self, parent, index, path, report):
        card = ttk.Frame(parent, style="Panel.TFrame", padding=8)
        card.pack(fill="x", pady=(0, 6))
        file = self.project.folder / path
        try:
            with Image.open(file) as image:
                image.thumbnail((180, 120))
                picture = ImageTk.PhotoImage(image)
            self.pictures.append(picture)
            ttk.Label(card, image=picture, style="Panel.TLabel").pack(side="left", padx=(0, 10))
        except Exception:
            ttk.Label(card, text="missing" if not file.exists() else "(no preview)",
                      style="Panel.TLabel").pack(side="left", padx=(0, 10))
        details = ttk.Frame(card, style="Panel.TFrame")
        details.pack(side="left", fill="x", expand=True, anchor="n")
        lines = [Path(path).name]
        if report:
            lines.append(f"{report.width_px} × {report.height_px} px")
            if report.dpi:
                lines.append(f"{report.dpi:.0f} dpi printed" + ("  ⚠" if report.dpi < 300 else ""))
            lines.append(f"AI: {report.verdict()}")
            for extra in (report.declared, report.traces, report.ai_note):
                if extra:
                    lines.append(extra)
            if report.ai_score is not None:
                lines.append(f"Classifier: {report.ai_score:.0%} likely AI")
            if report.duplicate_of:
                lines.append(f"⚠ same as {Path(report.duplicate_of).name}")
        ttk.Label(details, text="\n".join(lines), style="Panel.TLabel", wraplength=380,
                  justify="left").pack(anchor="w")
        row = ttk.Frame(details, style="Panel.TFrame")
        row.pack(anchor="w", pady=(4, 0))
        ttk.Button(row, text="Replace…", width=10, command=lambda: self.choose(index)).pack(side="left")
        ttk.Button(row, text="Remove", width=8, command=lambda: self.window.remove_image(index)
                   ).pack(side="left", padx=4)

    def choose(self, index):
        file = filedialog.askopenfilename(parent=self, filetypes=IMAGE_TYPES)
        if file:
            self.window.set_image(Path(file), index)

    def save(self) -> str:
        caption = self.caption.get("1.0", "end").strip()
        if caption == self.block.caption:
            return ""
        self.project.set_caption(self.key, caption)
        return "Caption saved."


class TableEditor(Editor):

    def __init__(self, parent, window, block, problems, number):
        super().__init__(parent, window, block.id, f"Table {number}", problems)
        self.block = block
        self.label("Caption (IEEE puts it above the table)")
        self.caption = entry(self, block.caption)
        self.caption.pack(fill="x")
        self.cells = []
        grid = ttk.Frame(self)
        grid.pack(anchor="w", pady=(8, 0))
        rows = pandoc.table_rows(block.node[0])[0] if block.node else []
        for r, row in enumerate(rows):
            for c, cell in enumerate(row[1]):
                field = entry(grid, pandoc.stringify(cell[4]).replace("\n", " ").strip())
                field.configure(width=14)
                field.grid(row=r, column=c, padx=1, pady=1)
                self.cells.append((cell, field))
        if not rows:
            self.label("This table has no cells to edit.", hint=True)
        self.block_buttons()

    def save(self) -> str:
        changed = False
        for cell, field in self.cells:
            old = pandoc.stringify(cell[4]).replace("\n", " ").strip()
            if field.get().strip() != old:
                cell[4] = [{"t": "Plain", "c": [{"t": "Str", "c": field.get().strip()}]}]
                changed = True
        caption = self.caption.get().strip()
        if caption != self.block.caption:
            self.block.caption = caption
            changed = True
        if changed:
            self.project.save()
        return "Table saved." if changed else ""


class ReferencesEditor(Editor):

    def __init__(self, parent, window, block, problems):
        super().__init__(parent, window, block.id, f"References ({len(block.entries)})", problems)
        self.block = block
        if self.project.m.bibliography:
            self.label(f"From {self.project.m.bibliography}. Edit that file to change them.", hint=True)
        self.text = text_box(self, "\n".join(block.entries), 14)
        self.text.pack(fill="both", expand=True)
        if self.project.m.bibliography:
            self.text.configure(state="disabled")
        self.block_buttons()

    def save(self) -> str:
        if self.project.m.bibliography:
            return ""
        lines = [line.strip() for line in self.text.get("1.0", "end").splitlines() if line.strip()]
        if lines == self.block.entries:
            return ""
        if self.block.keys and len(lines) != len(self.block.entries):
            raise ValueError("Keep one line for each cited reference.")
        self.block.entries = lines
        self.project.save()
        return "References saved."


def editor_for(parent, window, key, findings, reports):
    m = window.project.m
    if key in ("title", "authors", "abstract", "keywords"):
        return FrontEditor(parent, window, key, [f for f in findings if f.code.startswith("META")])
    block = m.find(key)
    problems = [f for f in findings if f.block_id == key]
    if block.kind == "figure":
        return FigureEditor(parent, window, block, problems, m.figures().index(block) + 1, reports)
    if block.kind == "table":
        return TableEditor(parent, window, block, problems, m.tables().index(block) + 1)
    if block.kind == "references":
        return ReferencesEditor(parent, window, block, problems)
    return TextEditor(parent, window, block, problems)

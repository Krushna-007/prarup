"""The tabs under the editor: Missing, Images, PDF checks, Figure fit, Notes.
Clicking a row that belongs to a block opens that block."""

from pathlib import Path
from tkinter import ttk

from prarup.ui.style import ERROR, WARNING, text_box


class ProblemList(ttk.Frame):
    """A list of rows; each row may remember the block it belongs to."""

    def __init__(self, parent, columns, widths, on_jump):
        super().__init__(parent)
        self.on_jump = on_jump
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        for name, width in zip(columns, widths):
            self.tree.heading(name, text=name, anchor="w")
            self.tree.column(name, width=width, stretch=(name == columns[-1]))
        self.tree.tag_configure("error", foreground=ERROR)
        self.tree.tag_configure("warning", foreground=WARNING)
        scroll = ttk.Scrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._clicked)
        self.blocks = {}                   # row id -> block id

    def fill(self, rows):
        """rows: (values, severity, block_id)"""
        self.tree.delete(*self.tree.get_children())
        self.blocks = {}
        for values, severity, block_id in rows:
            row = self.tree.insert("", "end", values=values, tags=(severity,))
            self.blocks[row] = block_id

    def _clicked(self, _event):
        rows = self.tree.selection()
        if rows and self.blocks.get(rows[0]):
            self.on_jump(self.blocks[rows[0]])


class Panels(ttk.Notebook):
    def __init__(self, parent, on_jump):
        super().__init__(parent)
        self.missing = ProblemList(self, ("Code", "What is wrong"), (80, 500), on_jump)
        self.images = ProblemList(self, ("Fig.", "File", "Pixels", "Printed dpi", "AI evidence"),
                                  (44, 140, 90, 90, 300), on_jump)
        self.checks = ProblemList(self, ("Code", "PDF check"), (80, 500), on_jump)
        self.fit = text_box(self, "Click Fit figures to make figure text readable.", 6)
        self.notes = text_box(self, "", 6)
        for widget, name in [(self.missing, "Missing"), (self.images, "Images"),
                             (self.checks, "PDF checks"), (self.fit, "Figure fit"),
                             (self.notes, "Notes")]:
            self.add(widget, text=name)

    def show_findings(self, findings, reports, notes):
        missing = [f for f in findings if f.group != "Images"]
        self.missing.fill([((f.code, f.message), f.severity, f.block_id) for f in missing])
        image_rows = []
        problems = {f.block_id for f in findings if f.group == "Images"}
        for r in reports:
            ai = r.verdict()
            detail = r.declared or r.traces or r.ai_note
            if r.duplicate_of:
                detail = f"same as {Path(r.duplicate_of).name}. " + detail
            severity = "error" if r.declared else ("warning" if r.block_id in problems else "")
            image_rows.append(((r.figure, Path(r.path).name, f"{r.width_px}×{r.height_px}",
                                f"{r.dpi:.0f}", f"{ai}. {detail}".strip(". ")), severity, r.block_id))
        self.images.fill(image_rows)
        self.set_text(self.notes, "\n".join(notes) or "Nothing to note.")
        self.tab(0, text=f"Missing ({len(missing)})")
        self.tab(1, text=f"Images ({len(findings) - len(missing)})")

    def show_checks(self, issues):
        self.checks.fill([((i.code, i.message), i.severity, "") for i in issues])
        self.tab(2, text=f"PDF checks ({len(issues)})")

    def show_fit(self, lines):
        self.set_text(self.fit, "\n".join(lines))
        self.select(self.fit)

    @staticmethod
    def set_text(box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

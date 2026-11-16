import sys
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from prarup import pandoc
from prarup.checks import run_all_checks
from prarup.fit import describe
from prarup.fix import embed_fonts
from prarup.models import Rules
from prarup.project import Project
from prarup.ui.preview import PdfPreview


class MainWindow:
    def __init__(self, root):
        self.root = root
        root.title("Prarup")
        width = min(1050, int(root.winfo_screenwidth() * 0.92))
        height = min(700, int(root.winfo_screenheight() * 0.85))
        root.geometry(f"{width}x{height}+40+30")
        root.minsize(760, 520)
        background = "#f2f4f7"
        ink = "#243247"
        root.configure(background=background)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=background)
        style.configure("TLabel", background=background, foreground=ink)
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(9, 5), background="#ffffff", foreground=ink)
        style.map("TButton", background=[("active", "#e5ecf6")])
        style.configure("Build.TButton", background="#2359a8", foreground="white")
        style.map("Build.TButton", background=[("disabled", "#e1e6ee"), ("active", "#194681")],
                  foreground=[("disabled", "#56657b"), ("!disabled", "white")])
        self.project = None
        self.rules = Rules.load(Path(__file__).resolve().parents[1] / "presets" / "ieee.yaml")
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.status = tk.StringVar(root, value="Open a Word or LaTeX manuscript.")
        root.protocol("WM_DELETE_WINDOW", self.close)

        bar = ttk.Frame(root, padding=(14, 12))
        bar.pack(fill="x")
        self.buttons = []
        for label, action in [
            ("Open", self.choose_file), ("Check", self.check), ("Build PDF", self.build),
            ("Fit figures", self.fit), ("Fix PDF", self.fix), ("Export ZIP", self.export),
        ]:
            style_name = "Build.TButton" if label == "Build PDF" else "TButton"
            button = ttk.Button(bar, text=label, command=action, style=style_name)
            button.pack(side="left", padx=(0, 5))
            self.buttons.append(button)

        ttk.Label(root, textvariable=self.status, anchor="w", padding=(14, 8)).pack(side="bottom", fill="x")
        panes = tk.PanedWindow(root, sashwidth=10, background=background, borderwidth=0)
        panes.pack(fill="both", expand=True, padx=14)
        left = ttk.Frame(panes, padding=(0, 0, 6, 0))
        right = ttk.Frame(panes)
        panes.add(left, width=462, minsize=400)
        panes.add(right, minsize=300)

        ttk.Label(left, text="Manuscript", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        outline = ttk.Frame(left)
        outline.pack(fill="x")
        scroll = ttk.Scrollbar(outline)
        scroll.pack(side="right", fill="y")
        self.outline = tk.Listbox(outline, height=9, yscrollcommand=scroll.set, exportselection=False,
                                  foreground=ink, selectbackground="#2359a8", selectforeground="white",
                                  borderwidth=0, highlightthickness=1, highlightbackground="#ccd5e1",
                                  highlightcolor="#2359a8", activestyle="none")
        self.outline.pack(fill="x")
        scroll.config(command=self.outline.yview)
        self.outline.bind("<Double-Button-1>", lambda event: self.edit())
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(7, 12))
        for label, command in [
            ("Edit", self.edit), ("Image", self.image), ("Add", self.add),
            ("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1)),
            ("Delete", self.delete),
        ]:
            button = ttk.Button(actions, text=label, command=command, width=7)
            button.pack(side="left", padx=(0, 3))
            self.buttons.append(button)

        ttk.Label(left, text="Report", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        self.report = ScrolledText(left, wrap="word", height=12, state="disabled", foreground=ink,
                                   background="white", borderwidth=0, highlightthickness=1,
                                   highlightbackground="#ccd5e1", padx=10, pady=8,
                                   font=("Segoe UI", 10))
        self.report.pack(fill="both", expand=True)
        self.preview = PdfPreview(right)
        self.enable()

    def enable(self):
        for i, button in enumerate(self.buttons):
            ready = not self.busy and (i == 0 or self.project is not None)
            button.config(state="normal" if ready else "disabled")

    def run(self, text, task, done):
        if self.busy:
            return
        self.busy = True
        self.enable()
        self.status.set(text)
        future = self.worker.submit(task)

        def finish():
            if not future.done():
                self.root.after(80, finish)
                return
            self.busy = False
            self.enable()
            try:
                done(future.result())
            except Exception as error:
                self.status.set("Operation failed")
                messagebox.showerror("Prarup", str(error), parent=self.root)

        self.root.after(80, finish)

    def close(self):
        if self.busy:
            messagebox.showinfo("Prarup", "Wait for the current operation to finish.", parent=self.root)
            return
        self.worker.shutdown()
        self.root.destroy()

    def choose_file(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Manuscripts", "*.docx *.tex *.zip")])
        if path:
            self.open_file(Path(path))

    def open_file(self, path):
        self.run("Opening manuscript...", lambda: Project.open(path), self.opened)

    def opened(self, project):
        self.project = project
        self.root.title(f"Prarup - {project.source.name}")
        self.preview.load()
        self.refresh("")
        self.check()

    def refresh(self, key=None):
        if key is None and self.outline.curselection():
            key = self.keys[self.outline.curselection()[0]]
        m = self.project.m
        self.keys = ["title", "authors", "abstract", "keywords"] + [b.id for b in m.blocks]
        self.outline.delete(0, "end")
        for name in self.keys[:4]:
            self.outline.insert("end", name.title())
        for block in m.blocks:
            text = block.caption or block.text or " ".join(block.images)
            title = " ".join(text.split())[:60]
            self.outline.insert("end", f"{block.kind.title()}  {title}")
        if key in self.keys:
            row = self.keys.index(key)
            self.outline.selection_set(row)
            self.outline.see(row)

    def selection(self):
        rows = self.outline.curselection()
        return self.keys[rows[0]] if rows else None

    def edit(self):
        if self.busy or not self.project or not self.selection():
            return
        key = self.selection()
        project = self.project
        block = project.m.find(key)
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit " + (block.kind if block else key))
        dialog.transient(self.root)
        dialog.grab_set()
        kind = None
        if block is None:
            value = getattr(project.m, key)
            if key == "authors":
                tk.Label(dialog, text="One author per line: name | affiliation").pack()
                value = "\n".join(f"{a.name} | {a.affiliation}" for a in value)
        elif block.kind in ("figure", "table"):
            tk.Label(dialog, text="Caption").pack()
            value = block.caption
        elif block.kind == "references":
            value = "\n".join(block.entries)
        else:
            value = block.text
            if block.kind in ("heading", "para", "quote"):
                kind = tk.StringVar(dialog, value=block.kind)
                tk.OptionMenu(dialog, kind, "para", "heading", "quote").pack()
        field = ScrolledText(dialog, width=64, height=12, wrap="word")
        field.insert("1.0", value)
        field.pack(padx=8, pady=8)
        if block and block.kind == "references" and project.m.bibliography:
            field.config(state="disabled")
            return

        def save():
            value = field.get("1.0", "end-1c").strip()
            try:
                if key == "authors":
                    rows = [line.partition("|") for line in value.splitlines() if line.strip()]
                    authors = [(name.strip(), affiliation.strip()) for name, _, affiliation in rows if name.strip()]
                    project.set_front(authors=authors)
                elif block is None:
                    project.set_front(**{key: value})
                elif block.kind in ("figure", "table"):
                    project.set_caption(key, value)
                elif block.kind == "references":
                    lines = [line.strip() for line in value.splitlines() if line.strip()]
                    if block.keys and len(lines) != len(block.entries):
                        raise ValueError("Keep one line per existing citation key.")
                    block.entries = lines
                    project.save()
                else:
                    project.set_text(key, value)
                    if kind and kind.get() != block.kind:
                        project.set_kind(key, kind.get())
            except (OSError, ValueError) as error:
                messagebox.showerror("Prarup", str(error), parent=dialog)
                return
            dialog.destroy()
            self.changed(key)

        tk.Button(dialog, text="Save", command=save).pack(pady=(0, 8))
        if block and block.kind == "table" and block.node:
            tk.Button(dialog, text="Edit a cell", command=lambda: self.edit_cell(dialog, block, save)).pack()
        field.focus_set()

    def edit_cell(self, dialog, block, save):
        rows, _ = pandoc.table_rows(block.node[0])
        if not rows:
            return
        row = simpledialog.askinteger("Table", "Row number", minvalue=1, maxvalue=len(rows), parent=dialog)
        if row is None or not rows[row - 1][1]:
            return
        cells = rows[row - 1][1]
        column = simpledialog.askinteger("Table", "Column number", minvalue=1, maxvalue=len(cells), parent=dialog)
        if column is not None:
            cell = cells[column - 1]
            old = pandoc.stringify(cell[4]).replace("\n", " ")
            text = simpledialog.askstring("Table", "Cell text", initialvalue=old, parent=dialog)
            if text is not None and text != old:
                cell[4] = [{"t": "Plain", "c": [{"t": "Str", "c": text}]}]
                save()

    def changed(self, key=None):
        self.refresh(key)
        self.preview.load()
        self.check()

    def image(self):
        block = self.project.m.find(self.selection())
        if not block or block.kind != "figure":
            return
        index = 0
        if block.images:
            names = "\n".join(f"{i}. {Path(path).name}" for i, path in enumerate(block.images, 1))
            number = simpledialog.askinteger("Image", names + "\nChoose an image to replace, or 0 to add.",
                                             minvalue=0, maxvalue=len(block.images), parent=self.root)
            if number is None:
                return
            index = number - 1 if number else len(block.images)
        path = filedialog.askopenfilename(parent=self.root)
        if path:
            self.project.set_image(block.id, Path(path), index)
            self.changed(block.id)

    def add(self):
        kind = simpledialog.askstring("Add a block", "Enter para, heading, or figure.", parent=self.root)
        if kind in ("para", "heading", "figure"):
            block = self.project.m.find(self.selection())
            added = self.project.insert(block.id if block else None, kind)
            self.changed(added.id)

    def move(self, step):
        block = self.project.m.find(self.selection())
        if block:
            self.project.move(block.id, step)
            self.changed(block.id)

    def delete(self):
        block = self.project.m.find(self.selection())
        if block and messagebox.askyesno("Delete", "Delete the selected block?", parent=self.root):
            self.project.delete(block.id)
            self.changed("title")

    def show_report(self, items, extra=""):
        lines = [f"{item.severity.upper()} {item.code}: {item.message}" for item in items]
        self.report.config(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("1.0", "\n\n".join(lines + ([extra] if extra else [])) or "No issues found.")
        self.report.config(state="disabled")

    def check(self):

        def done(items):
            result = self.project.last_build if self.preview.pdf else None
            self.show_report(items + (result.issues if result else []))
            self.status.set("Manuscript checked." if result else "Manuscript checked. Click Build PDF for PDF checks.")
        self.run("Checking manuscript...", self.project.findings, done)

    def build(self):
        self.preview.load()

        def task():
            return self.project.build(self.rules), self.project.findings()
        self.run("Building PDF...", task, self.built)

    def built(self, data):
        result, findings = data
        self.preview.load(result.pdf)
        self.show_report(findings + result.issues, "" if result.ok else result.log)
        self.status.set(f"Built PDF. {result.pages} pages." if result.ok else "PDF build failed.")

    def fit(self):
        def done(options):
            chosen = options[0]
            if len(options) > 1:
                text = f"Use the layout with {options[1].pages_after} pages? Choose No to keep the more readable layout."
                if messagebox.askyesno("Fit figures", text, parent=self.root):
                    chosen = options[1]
            self.project.apply_fit(chosen)
            messagebox.showinfo("Fit figures", "\n".join(describe(chosen)), parent=self.root)
            self.build()
        self.run("Fitting figures...", lambda: self.project.fit(self.rules), done)

    def fix(self):
        if not self.preview.pdf:
            messagebox.showinfo("Fix PDF", "Build the PDF first.", parent=self.root)
            return
        result = self.project.last_build
        repairable = sum(issue.can_fix for issue in result.issues)
        if not repairable:
            text = "This PDF has no issues that Fix PDF can repair."
            self.status.set(text)
            messagebox.showinfo(
                "Fix PDF",
                text + "\n\nUse the manuscript editor for missing captions or references, "
                "and review the report for any other findings.",
                parent=self.root,
            )
            return
        destination = result.pdf.with_name("paper-fixed.pdf")

        def task():
            embed_fonts(self.project.folder / "build" / "paper.pdf", destination)
            issues = run_all_checks(destination, self.rules)
            result.pdf = destination
            result.issues = issues
            return result, self.project.findings()

        def done(data):
            self.built(data)
            remaining = sum(issue.can_fix for issue in result.issues)
            if remaining:
                detail = f"{remaining} repairable PDF issue(s) remain. See the report."
            else:
                detail = f"Cleared {repairable} repairable PDF issue(s)."
            self.status.set(f"Saved {destination.name}. {detail}")

        self.run("Repairing PDF...", task, done)

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".zip",
                                          filetypes=[("Submission archive", "*.zip")])
        if path:
            self.preview.load()

            def done(saved):
                self.preview.load(self.project.last_build.pdf)
                self.status.set(f"Saved {saved.name}")

            self.run("Exporting...", lambda: self.project.export(Path(path), self.rules), done)


def main():
    root = tk.Tk()
    window = MainWindow(root)
    if len(sys.argv) > 1:
        window.open_file(Path(sys.argv[1]))
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

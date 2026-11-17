import sys
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from prarup import images
from prarup.checks import run_all_checks
from prarup.fit import describe
from prarup.fix import embed_fonts
from prarup.models import Rules
from prarup.project import Project
from prarup.ui import style
from prarup.ui.editors import editor_for
from prarup.ui.outline import Outline
from prarup.ui.panels import Panels
from prarup.ui.preview import PdfPreview

PAPERS = [("Papers", "*.docx *.tex *.zip")]
REBUILD_AFTER_MS = 1500


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.project = None
        self.rules = Rules.load(Path(__file__).resolve().parents[1] / "presets" / "ieee.yaml")
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.rebuild_timer = None
        self.rebuild_waiting = False
        self.findings, self.key, self.editor = [], None, None
        self.choose_fit = self.ask_fit
        self.classify = tk.BooleanVar(root, value=False)
        self.status = tk.StringVar(root, value="Open a Word (.docx), LaTeX (.tex) or zipped LaTeX paper.")

        root.title("Prarup")
        root.geometry("1440x880")
        root.minsize(1000, 620)
        style.apply(root)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.make_toolbar()
        ttk.Label(root, textvariable=self.status, style="Status.TLabel").pack(side="bottom", fill="x")

        columns = ttk.PanedWindow(root, orient="horizontal")
        columns.pack(fill="both", expand=True)
        self.outline = Outline(columns, self.show_block)
        middle = ttk.PanedWindow(columns, orient="vertical")
        self.editor_area = ttk.Frame(middle)
        self.panels = Panels(middle, self.jump)
        middle.add(self.editor_area, weight=3)
        middle.add(self.panels, weight=2)
        right = ttk.Frame(columns, padding=6)
        self.preview = PdfPreview(right)
        columns.add(self.outline, weight=2)
        columns.add(middle, weight=4)
        columns.add(right, weight=3)
        self.middle = middle
        root.after(200, self.place_dividers)
        self.enable()

    def place_dividers(self):
        self.root.update_idletasks()
        self.middle.sashpos(0, int(self.middle.winfo_height() * 0.6))

    def make_toolbar(self):
        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="प्रारूप Prarup", style="Brand.TLabel").pack(side="left", padx=(0, 14))
        self.buttons = {}
        for name, command in [("Open", self.choose_file), ("Build", self.build),
                              ("Fit figures", self.fit), ("Fix PDF", self.fix),
                              ("Export", self.export)]:
            button = ttk.Button(bar, text=name, command=command, width=len(name) + 2,
                                style="Accent.TButton" if name == "Build" else "TButton")
            button.pack(side="left", padx=(0, 4))
            self.buttons[name] = button
        ai = ttk.Checkbutton(bar, text="AI classifier", variable=self.classify, command=self.toggle_ai)
        ai.pack(side="left", padx=10)
        if not images.classifier_installed():
            ai.configure(state="disabled", text="AI classifier (not installed)")
        self.file_label = ttk.Label(bar, text="", style="File.TLabel")
        self.file_label.pack(side="right")

    def enable(self):
        for name, button in self.buttons.items():
            ready = not self.busy and (name == "Open" or self.project is not None)
            if name == "Fix PDF":
                ready = ready and self.preview.pdf is not None
            button.configure(state="normal" if ready else "disabled")

    def run(self, message, job, done):
        if self.busy:
            return
        self.busy = True
        self.enable()
        self.status.set(message)
        future = self.worker.submit(job)

        def check():
            if not future.done():
                self.root.after(80, check)
                return
            self.busy = False
            try:
                done(future.result())
            except Exception as error:
                self.status.set("Failed: " + str(error).splitlines()[0][:120])
                messagebox.showerror("Prarup", str(error)[:2000], parent=self.root)
            self.enable()
            if self.rebuild_waiting:
                self.rebuild_waiting = False
                self.build()

        self.root.after(80, check)

    def close(self):
        if self.busy:
            messagebox.showinfo("Prarup", "Wait for the current job to finish.", parent=self.root)
            return
        self.worker.shutdown()
        self.root.destroy()

    def choose_file(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=PAPERS)
        if path:
            self.open_file(Path(path))

    def open_file(self, path):
        self.save_editor(quiet=True)
        self.run(f"Opening {Path(path).name}…", lambda: Project.open(Path(path)), self.opened)

    def opened(self, project):
        self.project, self.key = project, None
        self.root.title(f"Prarup - {project.source.name}")
        self.file_label.configure(text=f"{project.source.name}  ·  IEEE Conference")
        self.preview.load()
        self.panels.show_checks([])
        self.refresh()
        self.outline.select("title")
        self.status.set(f"Opened {project.source.name}: {len(self.findings)} item(s) to look at. "
                        "Click Build for the PDF.")
        self.schedule_build(0)

    def refresh(self):
        self.findings = self.project.findings(self.classify.get())
        self.outline.show(self.project.m, self.findings)
        self.panels.show_findings(self.findings, self.project.reports, self.project.m.notes)
        if self.key and (self.key in ("title", "authors", "abstract", "keywords")
                         or self.project.m.find(self.key)):
            self.make_editor(self.key)
        else:
            self.make_editor(None)

    def show_block(self, key):
        if key == self.key:
            return
        message = self.save_editor(quiet=True)
        if message:
            self.refresh_after_edit(message, key)
        else:
            self.make_editor(key)

    def make_editor(self, key):
        if self.editor is not None:
            self.editor.destroy()
        self.key, self.editor = key, None
        if key:
            self.editor = editor_for(self.editor_area, self, key, self.findings, self.project.reports)
            self.editor.pack(fill="both", expand=True)

    def jump(self, block_id):
        self.outline.select(block_id)
        self.show_block(block_id)

    def save_editor(self, quiet=False):
        if self.editor is None:
            return ""
        try:
            message = self.editor.save()
        except ValueError as error:
            messagebox.showerror("Prarup", str(error), parent=self.root)
            return ""
        if not quiet:
            if message:
                self.refresh_after_edit(message)
            else:
                self.status.set("Nothing to save.")
        return message

    def refresh_after_edit(self, message, key=None):
        if key:
            self.key = key
        self.refresh()
        if self.key:
            self.outline.select(self.key)
        self.status.set(message + " Rebuilding the PDF shortly…")
        self.schedule_build()

    def move(self, step):
        self.save_editor(quiet=True)
        self.project.move(self.key, step)
        self.refresh_after_edit("Moved.")

    def insert(self, kind):
        self.save_editor(quiet=True)
        block = self.project.insert(self.key, kind, "New paragraph." if kind == "para" else "")
        self.refresh_after_edit(f"Added a {kind}.", block.id)

    def delete_block(self):
        if messagebox.askyesno("Delete", "Delete this block?", parent=self.root):
            self.project.delete(self.key)
            self.key = None
            self.refresh_after_edit("Deleted.")

    def set_image(self, file, index):
        self.save_editor(quiet=True)
        self.project.set_image(self.key, file, index)
        self.refresh_after_edit("Image saved.")

    def remove_image(self, index):
        self.save_editor(quiet=True)
        self.project.remove_image(self.key, index)
        self.refresh_after_edit("Image removed.")

    def toggle_ai(self):
        if self.project:
            self.refresh()
            self.status.set("AI classifier on: it runs on photos, never on charts."
                            if self.classify.get() else "AI classifier off.")

    def schedule_build(self, delay=REBUILD_AFTER_MS):
        if self.rebuild_timer:
            self.root.after_cancel(self.rebuild_timer)
        self.rebuild_timer = self.root.after(delay, self.build)

    def build(self):
        self.rebuild_timer = None
        if self.project is None:
            return
        if self.busy:
            self.rebuild_waiting = True
            return
        self.save_editor(quiet=True)
        self.run("Building the IEEE PDF…", lambda: self.project.build(self.rules), self.built)

    def built(self, result):
        self.preview.load(result.pdf)
        self.panels.show_checks(result.issues)
        if result.ok:
            self.status.set(f"Built: {result.pages} pages, {len(result.issues)} PDF check(s), "
                            f"{len(self.findings)} item(s) in Missing and Images.")
        else:
            self.status.set("The PDF did not build. See the message.")
            messagebox.showerror("LaTeX error", result.log[-2000:], parent=self.root)

    def fit(self):
        self.save_editor(quiet=True)
        self.run("Fitting figures: compiling a few layouts…", lambda: self.project.fit(self.rules),
                 self.fitted)

    def fitted(self, options):
        chosen = options[0] if len(options) == 1 else self.choose_fit(*options)
        if chosen is None:
            self.status.set("Figures left as they were.")
            return
        self.project.apply_fit(chosen)
        self.panels.show_fit(describe(chosen))
        self.refresh()
        self.status.set("Figures fitted. Building…")
        self.root.after(0, self.build)

    def ask_fit(self, readable, within):
        answer = messagebox.askyesnocancel(
            "Fit figures",
            f"Readable figures need {readable.pages_after} pages, over the limit of "
            f"{readable.page_limit}.\nSmaller figures fit in {within.pages_after} pages, "
            "but some text falls below the minimum size.\n\n"
            "Yes: readable figures.   No: stay within the page limit.",
            parent=self.root)
        if answer is None:
            return None
        return readable if answer else within

    def fix(self):
        result = self.project.last_build
        if not any(issue.can_fix for issue in result.issues):
            messagebox.showinfo("Fix PDF", "Nothing in this PDF can be repaired automatically. "
                                "Fix the items in Missing with the editor.", parent=self.root)
            return
        fixed = result.pdf.with_name("paper-fixed.pdf")

        def job():
            embed_fonts(result.pdf, fixed)
            result.pdf, result.issues = fixed, run_all_checks(fixed, self.rules)
            return result
        self.run("Repairing the PDF with Ghostscript…", job, self.built)

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".zip",
                                            initialfile=f"{self.project.source.stem}-submission.zip",
                                            filetypes=[("Zip", "*.zip")])
        if path:
            self.export_to(Path(path))

    def export_to(self, path):
        self.save_editor(quiet=True)
        self.run("Exporting…", lambda: self.project.export(path, self.rules),
                 lambda saved: self.status.set(f"Saved {saved.name}: PDF, LaTeX, images and report."))


def main():
    root = tk.Tk()
    window = MainWindow(root)
    if len(sys.argv) > 1:
        window.open_file(Path(sys.argv[1]))
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())

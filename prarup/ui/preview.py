import tkinter as tk
from tkinter import ttk

import pymupdf


class PdfPreview:
    def __init__(self, parent):
        self.pdf = None
        self.page = 0
        pages = ttk.Frame(parent)
        pages.pack(fill="x", pady=(0, 6))
        self.previous = ttk.Button(pages, text="Previous", command=lambda: self.draw(-1))
        self.previous.pack(side="left")
        self.next = ttk.Button(pages, text="Next", command=lambda: self.draw(1))
        self.next.pack(side="right")
        self.page_label = ttk.Label(pages, text="PDF preview", style="Section.TLabel")
        self.page_label.pack()
        self.preview_area = tk.Canvas(parent, background="#e1e7ef", highlightthickness=0)
        self.preview_area.pack(fill="both", expand=True)
        self.preview_area.bind("<Configure>", lambda event: self.draw())

    def load(self, path=None):
        self.pdf = path
        self.page = 0
        self.draw()

    def draw(self, step=0):
        self.preview_area.delete("all")
        if not self.pdf:
            self.page_label.config(text="PDF preview")
            return
        with pymupdf.open(self.pdf) as doc:
            total_pages = len(doc)
            self.page = max(0, min(self.page + step, total_pages - 1))
            page = doc[self.page]
            width = max(1, self.preview_area.winfo_width() - 12)
            height = max(1, self.preview_area.winfo_height() - 12)
            scale = min(width / page.rect.width, height / page.rect.height)
            pixels = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB)
            self.picture = tk.PhotoImage(master=self.preview_area, data=pixels.tobytes("ppm"))
        self.preview_area.create_image((width + 12) // 2, 6, image=self.picture, anchor="n")
        self.page_label.config(text=f"Page {self.page + 1} / {total_pages}")

"""Screenshots of the window working on a damaged real paper, for the docs.

    poetry run python tools/walkthrough.py

Opens tests/fixtures/messy/svm_messy.docx in a temporary folder, takes the
same steps as tests/test_messy.py, and saves docs/images/walkthrough/*.png.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from prarup.ui.window import MainWindow  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images" / "walkthrough"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    paper = tmp / "svm_messy.docx"
    shutil.copy(ROOT / "tests" / "fixtures" / "messy" / "svm_messy.docx", paper)

    app = QApplication(sys.argv)
    app.setStyleSheet((ROOT / "prarup" / "ui" / "style.qss").read_text())
    w = MainWindow()
    w.resize(1600, 940)
    w.show()

    def settle(seconds=0.5):
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    def idle():
        settle(0.3)
        while w.busy or w.rebuild_pending or w.workers or w.rebuild_timer.isActive():
            app.processEvents()
            time.sleep(0.05)
        settle(0.8)

    def shot(name):
        w.grab().save(str(OUT / f"{name}.png"))
        print("saved", name)

    w.open_file(paper)
    idle()
    shot("1-opened-missing")

    w.panels.setCurrentWidget(w.panels.images)
    ai = next(f for f in w.project.m.figures() if "Overview" in f.caption)
    w.outline.select(ai.id)
    settle()
    shot("2-ai-image-found")

    w.outline.select("front:abstract")
    w.editor.abstract.setPlainText("We classify diabetes with a support vector machine on the PIMA "
                                   "dataset and compare kernels before and after pre-processing.")
    w.editor.keywords.setText("SVM, diabetes, PIMA dataset")
    w.save_editor()
    plot = ROOT / "tests" / "fixtures" / "latex_project" / "figs" / "accuracy.png"
    w.outline.select(ai.id)
    w.editor.set_image(plot, 0)
    duplicate = next(f for f in w.project.m.figures() if "again" in f.caption)
    w.outline.select(duplicate.id)
    w.editor._delete()
    idle()
    no_caption = next(f for f in w.project.m.figures() if f.images and not f.caption)
    w.outline.select(no_caption.id)
    settle()
    shot("3-fixing-a-caption")

    w.choose_fit = lambda readable, within: readable
    w.fit()
    idle()
    shot("4-figures-fitted")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

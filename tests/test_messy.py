"""End to end, through the window: damaged real papers are opened, every
damage is found in the right panel, fixed with the editors as a user would,
then fitted, built and exported. See fixtures/messy/README.md."""

import shutil
import zipfile
from pathlib import Path

import pytest

from prarup.ui.window import MainWindow

FIX = Path(__file__).parent / "fixtures"
MESSY = FIX / "messy"
PLOT = FIX / "latex_project" / "figs" / "accuracy.png"

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None or shutil.which("tectonic") is None,
    reason="pandoc and tectonic needed")


def idle(qtbot, w, timeout=300_000):
    qtbot.waitUntil(lambda: not w.busy and not w.rebuild_pending and not w.workers
                    and not w.rebuild_timer.isActive(), timeout=timeout)


def opened(qtbot, tmp_path, name):
    shutil.copy(MESSY / name, tmp_path / name)
    w = MainWindow()
    qtbot.addWidget(w)
    w.open_file(tmp_path / name)
    idle(qtbot, w)
    return w


def panel(widget):
    return "\n".join(widget.item(i).text() for i in range(widget.count()))


def hires_plot(tmp_path, name: str, curve) -> Path:
    """A distinct plot at 1200 px: enough for 300 dpi at column width."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.plot(range(10), [curve(x) for x in range(10)])
    ax.set_xlabel("epoch")
    fig.tight_layout()
    path = tmp_path / f"{name}.png"
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path


def test_svm_every_damage_is_found_and_fixed(qtbot, tmp_path):
    w = opened(qtbot, tmp_path, "svm_messy.docx")
    missing, images = panel(w.panels.missing), panel(w.panels.images)
    for expected in ["META-03", "META-04", "FIG-01", "FIG-03"]:
        assert expected in missing
    for expected in ["IMG-01", "IMG-02", "IMG-05", "Created by Google Generative AI"]:
        assert expected in images

    # the title block
    w.outline.select("front:abstract")
    w.editor.abstract.setPlainText("We classify diabetes with a support vector machine on the PIMA data.")
    w.editor.keywords.setText("SVM, diabetes, PIMA")
    w.save_editor()

    m = w.project.m
    figures = m.figures()
    ai = next(f for f in figures if "Overview" in f.caption)
    no_caption = next(f for f in figures if f.images and not f.caption)
    no_image = next(f for f in figures if not f.images)
    duplicate = next(f for f in figures if "again" in f.caption)
    w.outline.select(ai.id)
    w.editor.set_image(hires_plot(tmp_path, "pipeline", lambda x: x * x), 0)   # AI image replaced
    w.outline.select(no_caption.id)
    w.editor.caption.setPlainText("The SVM technique.")
    w.save_editor()
    w.editor.set_image(hires_plot(tmp_path, "svm", lambda x: 10 - x), 0)       # low-res replaced
    w.outline.select(no_image.id)
    w.editor.set_image(hires_plot(tmp_path, "method", lambda x: x % 3), 0)     # drawing supplied
    w.outline.select(duplicate.id)
    w.editor._delete()                                    # the duplicate removed
    idle(qtbot, w)

    missing, images = panel(w.panels.missing), panel(w.panels.images)
    for gone in ["META-03", "META-04", "FIG-01", "FIG-03"]:
        assert gone not in missing
    for gone in ["IMG-02", "IMG-05", "117 dpi"]:
        assert gone not in images
    assert "217 dpi" in images             # a real low-resolution image in the original paper
    assert w.project.last_build.ok

    w.export_to(tmp_path / "svm-submission.zip")
    idle(qtbot, w)
    report = zipfile.ZipFile(tmp_path / "svm-submission.zip").read("prarup-report.md").decode()
    assert "IMG-02" not in report and "META-03" not in report


def test_uav_citation_past_the_references_is_found(qtbot, tmp_path):
    w = opened(qtbot, tmp_path, "uav_messy.docx")
    missing = panel(w.panels.missing)
    assert "REF-02  Citation [99] points past the 50 references." in missing
    assert "META-04" in missing and "FIG-01" in missing
    row = next(i for i in range(w.panels.missing.count()) if "[99]" in w.panels.missing.item(i).text())
    w.panels._clicked(w.panels.missing.item(row))
    assert "99\\]" in w.editor.text.toPlainText()          # jumped to the paragraph with it (Markdown: \\[99\\])
    w.editor.text.setPlainText(w.editor.text.toPlainText().replace("\\[99\\]", "").replace("[99]", ""))
    w.save_editor()
    idle(qtbot, w)
    assert "[99]" not in panel(w.panels.missing)


def test_zipped_latex_project_end_to_end(qtbot, tmp_path):
    w = opened(qtbot, tmp_path, "latex_messy.zip")
    missing, images = panel(w.panels.missing), panel(w.panels.images)
    assert "REF-02  Citation [ghost] has no matching reference." in missing
    assert "IMG-02" in images and "70 dpi" in images
    assert w.project.last_build.ok and w.pdf.pageCount() >= 1

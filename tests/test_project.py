"""The controller: open, edit, check, build, fit, export, on real papers."""

import shutil
import zipfile
from pathlib import Path

import pytest

from prarup.models import Rules
from prarup.project import Project, _readable_error

REAL = Path(__file__).parent / "fixtures" / "real"
LATEX = Path(__file__).parent / "fixtures" / "latex_project"
IMAGES = Path(__file__).parent / "fixtures" / "images"

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None or shutil.which("tectonic") is None,
    reason="pandoc and tectonic needed")


@pytest.fixture
def svm(tmp_path):
    source = tmp_path / "svm.docx"
    shutil.copy(REAL / "svm_diabetes.docx", source)
    return Project.open(source)


def test_project_folder_sits_beside_the_paper(svm, tmp_path):
    assert svm.folder == tmp_path / "svm-prarup"
    assert (svm.folder / "manuscript.json").exists()


def test_edits_survive_closing_and_reopening(svm):
    fig = next(f for f in svm.m.figures() if f.number == 2)
    svm.set_caption(fig.id, "Support vector machine, the separating margin")
    svm.set_front(keywords="SVM, diabetes")
    again = Project.open(svm.source)
    assert again.m.find(fig.id).caption == "Support vector machine, the separating margin"
    assert again.m.keywords == "SVM, diabetes"


def test_a_changed_source_is_read_again(svm):
    svm.set_front(title="Edited title")
    svm.source.touch()
    assert Project.open(svm.source).m.title != "Edited title"


def test_filling_a_missing_image_clears_the_finding(svm):
    fig = next(f for f in svm.m.figures() if f.number == 1)
    assert any(f.code == "FIG-03" and f.block_id == fig.id for f in svm.findings())
    svm.set_image(fig.id, LATEX / "figs" / "accuracy.png")
    assert not any(f.code == "FIG-03" and f.block_id == fig.id for f in svm.findings())


def test_retag_a_boilerplate_heading_as_paragraph_then_delete_it(svm):
    junk = next(b for b in svm.m.blocks if b.kind == "heading" and "Suggested Citation" in b.text)
    svm.set_kind(junk.id, "para")
    assert svm.m.find(junk.id).kind == "para"
    svm.delete(junk.id)
    assert svm.m.find(junk.id) is None


def test_build_compiles_and_checks(svm):
    result = svm.build(Rules())
    assert result.ok and result.pages >= 4
    assert result.pdf.parent == svm.folder / "build"


def test_an_inserted_ai_image_is_caught_before_the_build(svm):
    fig = svm.insert(svm.m.blocks[5].id, "figure")
    svm.set_image(fig.id, IMAGES / "gemini_c2pa.jpg")
    svm.set_caption(fig.id, "Overview of the method")
    codes = [f.code for f in svm.findings()]
    assert "IMG-02" in codes


def test_export_bundle_has_everything(svm, tmp_path):
    out = svm.export(tmp_path / "submission.zip", Rules())
    names = zipfile.ZipFile(out).namelist()
    assert {"paper.pdf", "paper.tex", "prarup-report.md", "README.txt"} <= set(names)
    assert any(n.startswith("media/") for n in names)
    report = zipfile.ZipFile(out).read("prarup-report.md").decode()
    assert "FIG-03" in report                       # Fig. 1 still has no image


def test_fit_keeps_its_layout_for_later_builds(tmp_path):
    shutil.copytree(LATEX, tmp_path, dirs_exist_ok=True)
    project = Project.open(tmp_path / "main.tex")
    [report] = project.fit(Rules(page_limit=6))
    project.apply_fit(report)
    fig = project.m.figures()[0]
    assert fig.fit_width.endswith("columnwidth")         # remembered on the figure
    assert project.build(Rules()).ok
    assert f"width={fig.fit_width}" in project.tex_path().read_text()   # and used again


def test_compile_errors_are_shown_as_one_sentence():
    log = ("error: paper.tex:42: Undefined control sequence\n"
           "error: something bad happened inside XeTeX; its output follows:\n")
    assert _readable_error(log) == "LaTeX stopped at line 42 of paper.tex: Undefined control sequence"

import shutil
import zipfile
from pathlib import Path

import pytest

from prarup.models import Rules
from prarup.project import Project

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def project(tmp_path):
    if shutil.which("pandoc") is None:
        pytest.skip("Pandoc required")

    def open_copy(name):
        copy = tmp_path / name
        shutil.copyfile(FIXTURES / "messy" / name, copy)
        return Project.open(copy)

    return open_copy


def test_svm_damage_is_found_and_edits_clear_findings(project, tmp_path):
    paper = project("svm_messy.docx")
    findings = paper.findings()
    codes = {item.code for item in findings}
    assert {"META-03", "META-04", "FIG-01", "FIG-03", "IMG-01", "IMG-02", "IMG-05"} <= codes
    paper.set_front(abstract="We classify diabetes with a support vector machine.",
                    keywords="SVM, diabetes, PIMA")
    plot = FIXTURES / "latex_project" / "figs" / "accuracy.png"
    for figure in paper.m.figures():
        if not figure.caption:
            paper.set_caption(figure.id, "The SVM technique.")
        if not figure.images:
            paper.set_image(figure.id, plot)
    assert not {"META-03", "META-04", "FIG-01", "FIG-03"} & {item.code for item in paper.findings()}
    if shutil.which("tectonic"):
        with zipfile.ZipFile(paper.export(tmp_path / "submission.zip", Rules())) as bundle:
            assert "paper.pdf" in bundle.namelist()
            assert "META-03" not in bundle.read("prarup-report.md").decode()


def test_uav_citation_past_the_references_is_found(project):
    paper = project("uav_messy.docx")
    assert any(item.code == "REF-02" and "[99]" in item.message for item in paper.findings())
    paragraph = next(block for block in paper.m.blocks if "99\\]" in block.text or "[99]" in block.text)
    paper.set_text(paragraph.id, paragraph.text.replace("\\[99\\]", "").replace("[99]", ""))
    assert not any(item.code == "REF-02" and "[99]" in item.message for item in paper.findings())


def test_zipped_latex_project(project):
    paper = project("latex_messy.zip")
    findings = paper.findings()
    assert any(item.code == "REF-02" and "[ghost]" in item.message for item in findings)
    assert any(item.code == "IMG-01" and "70 dpi" in item.message for item in findings)
    if shutil.which("tectonic"):
        assert paper.build(Rules()).ok

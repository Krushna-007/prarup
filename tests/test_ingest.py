import shutil
from pathlib import Path

import pytest

from prarup.ingest import OpenFailed, open_paper
from prarup.manuscript import Manuscript

REAL = Path(__file__).parent / "fixtures" / "real"
LATEX = Path(__file__).parent / "fixtures" / "latex_project"

pytestmark = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")


@pytest.fixture(scope="module")
def yolo(tmp_path_factory):
    return open_paper(REAL / "yolo_football.docx", tmp_path_factory.mktemp("yolo"))


@pytest.fixture(scope="module")
def uav(tmp_path_factory):
    return open_paper(REAL / "uav_imagery.docx", tmp_path_factory.mktemp("uav"))


@pytest.fixture(scope="module")
def svm(tmp_path_factory):
    return open_paper(REAL / "svm_diabetes.docx", tmp_path_factory.mktemp("svm"))


@pytest.fixture(scope="module")
def latex(tmp_path_factory):
    project = tmp_path_factory.mktemp("latex")
    return open_paper(LATEX / "main.tex", project), project


def test_yolo_front_matter_skips_the_label_line(yolo):
    assert yolo.title.startswith("YOLO-Based Object Detection and Player Tracking")
    assert [a.name for a in yolo.authors] == ["Dipto Roy"]
    assert "Parul University" in yolo.authors[0].affiliation
    assert yolo.abstract.startswith("Performance analysis is essential")


def test_uav_numbered_affiliations_and_logo(uav):
    assert [a.name for a in uav.authors][:2] == ["Kayeleigh Sharp", "Brooklyn Christofis"]
    assert uav.authors[0].affiliation.startswith("Northern Arizona University")
    assert uav.keywords.startswith("machine learning, archaeology")
    assert any("logo" in n for n in uav.notes)


def test_svm_abstract_and_keywords_come_out_of_the_layout_table(svm):
    assert svm.title == "Support vector machine classification learning algorithm for diabetes prediction"
    assert svm.abstract.startswith("Diabetes is actually one of the primary causes")
    assert svm.keywords.startswith("Classification, Data analysis")


def test_latex_ieee_author_blocks_with_markers(latex):
    m, _ = latex
    assert [(a.name, a.affiliation) for a in m.authors] == [
        ("Asha Rao", "DA-IICT, Gandhinagar, India"),
        ("Vikram Shah", "IIT Bombay, Mumbai, India"),
        ("Om Patel", "DA-IICT, Gandhinagar, India"),
    ]
    assert m.keywords == "federated learning, UAV"
    assert m.abstract == "We study federated learning on UAV swarms and show a 12% gain."


def test_uncaptioned_word_figures_are_figures_with_no_caption(yolo):
    figures = yolo.figures()
    assert len(figures) == 3
    assert all(f.images and f.caption == "" for f in figures)


def test_caption_paragraph_after_the_image_is_joined_to_it(svm):
    fig = next(f for f in svm.figures() if f.number == 2)
    assert fig.caption == "SVM technique"
    assert fig.images == ["media/image2.png"]
    assert "after the image" in fig.detected


def test_caption_with_no_image_becomes_a_figure_without_one(svm):
    fig = next(f for f in svm.figures() if f.number == 1)
    assert fig.images == [] and fig.caption == "Proposed methodology"


def test_table_captions_before_and_after_their_tables(svm):
    captions = [t.caption for t in svm.tables()]
    assert "Attributes of dataset" in captions
    assert "Comparison between this study and previous studies" in captions


def test_sub_images_join_the_figure_captioned_together(uav):
    fig = next(f for f in uav.figures() if f.number == 4)
    assert len(fig.images) == 3
    assert fig.caption.startswith("a. Unsuccessful training")


def test_bold_paragraphs_become_section_headings(svm):
    headings = [b.text for b in svm.blocks if b.kind == "heading"]
    assert "INTRODUCTION" in headings and "CONCLUSION" in headings


def test_inline_maths_numbered_like_an_equation_is_an_equation(svm):
    equations = [b for b in svm.blocks if b.kind == "equation"]
    assert any("TP + TN" in e.text for e in equations)


def test_references_paragraph_collects_its_entries(yolo):
    [refs] = [b for b in yolo.blocks if b.kind == "references"]
    assert len(refs.entries) == 16
    assert refs.entries[0].startswith("Bialkowski")


def test_latex_input_files_are_followed(latex):
    m, _ = latex
    assert [b.text for b in m.blocks if b.kind == "heading"][:2] == ["Introduction", "Results"]


def test_latex_bibitems_keep_their_keys(latex):
    m, _ = latex
    [refs] = [b for b in m.blocks if b.kind == "references"]
    assert refs.keys == ["mcmahan", "unused"]


def test_latex_images_are_copied_and_case_mismatch_is_noted(latex):
    m, project = latex
    acc, missing = m.figures()
    assert acc.images == ["media/accuracy.png"] and (project / "media" / "accuracy.png").exists()
    assert acc.label == "fig:acc"
    assert any("breaks on Linux" in n for n in m.notes)
    assert missing.images == ["figs/missing_plot"]


def test_author_macros_are_carried_over_safely(latex):
    m, _ = latex
    assert r"\usepackage{dsfont}" in m.preamble
    assert r"\providecommand{\E}{\mathds{E}}" in m.preamble
    assert "inputenc" not in m.preamble


def test_manuscript_survives_a_save_and_load(latex, tmp_path):
    m, _ = latex
    m.save(tmp_path / "m.json")
    again = Manuscript.load(tmp_path / "m.json")
    assert again.title == m.title and again.authors == m.authors
    assert [b.kind for b in again.blocks] == [b.kind for b in m.blocks]


def test_unsupported_file_is_refused(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(OpenFailed):
        open_paper(tmp_path / "notes.txt", tmp_path / "p")


def test_a_zipped_latex_project_opens(tmp_path):
    archive = shutil.make_archive(str(tmp_path / "paper"), "zip", LATEX)
    m = open_paper(Path(archive), tmp_path / "project")
    assert m.title == "Federated Learning on Drone Swarms"
    assert (tmp_path / "project" / "media" / "accuracy.png").exists()

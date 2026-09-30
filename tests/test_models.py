import pytest

from prarup.models import Issue, Rules


def test_issue_holds_its_fields():
    issue = Issue("FONT-01", "Helvetica is not embedded", "error")
    assert issue.code == "FONT-01"
    assert issue.message == "Helvetica is not embedded"
    assert issue.severity == "error"


def test_issue_is_not_fixable_by_default():
    assert Issue("X", "m", "warning").can_fix is False


def test_rules_have_ieee_defaults():
    rules = Rules()
    assert rules.page_limit == 6
    assert rules.columns == 2


def test_rules_load_from_yaml(tmp_path):
    path = tmp_path / "ieee.yaml"
    path.write_text("page_limit: 8\ncolumns: 2\nbody_font_pt: 9.5\n")
    rules = Rules.load(path)
    assert rules.page_limit == 8
    assert rules.body_font_pt == 9.5


def test_missing_keys_fall_back_to_defaults(tmp_path):
    path = tmp_path / "partial.yaml"
    path.write_text("page_limit: 4\n")
    rules = Rules.load(path)
    assert rules.page_limit == 4
    assert rules.columns == 2          # default


def test_unknown_keys_are_rejected(tmp_path):
    """A typo in a rules file should be loud, not silently ignored."""
    path = tmp_path / "typo.yaml"
    path.write_text("page_limmit: 4\n")
    with pytest.raises(ValueError, match="page_limmit"):
        Rules.load(path)

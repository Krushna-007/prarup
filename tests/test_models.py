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

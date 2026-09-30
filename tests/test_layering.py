"""One architectural rule, enforced.

checks.py must stay free of anything that touches the outside world. That
is what keeps it fast to test and simple to reason about. If someone adds
a subprocess call to it, this test says so immediately.
"""

from pathlib import Path

CHECKS = Path(__file__).parent.parent / "prarup" / "checks.py"
FORBIDDEN = ["subprocess", "PySide6", "requests", "urllib", "socket"]


def test_checks_does_not_touch_the_outside_world():
    source = CHECKS.read_text()
    found = [name for name in FORBIDDEN if name in source]
    assert found == [], f"checks.py should not use: {found}"

from pathlib import Path

CHECKS = Path(__file__).parent.parent / "prarup" / "checks.py"
FORBIDDEN = ["subprocess", "tkinter", "requests", "urllib", "socket"]


def test_checks_does_not_touch_the_outside_world():
    source = CHECKS.read_text()
    found = [name for name in FORBIDDEN if name in source]
    assert found == [], f"checks.py should not use: {found}"

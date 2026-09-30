"""Shared test setup.

Qt needs a platform plugin. Forcing "offscreen" means the GUI tests run
without a display, so they work over ssh and in CI.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

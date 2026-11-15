"""Run slow work (pandoc, Tectonic, the classifier) off the UI thread."""

from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Runs job() in a thread; reports through Qt signals, delivered on the UI thread."""

    done = Signal(object)
    failed = Signal(str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job

    def run(self) -> None:
        try:
            result = self.job()
        except Exception as exc:              # noqa: BLE001 - every failure is shown to the user
            self.failed.emit(f"{type(exc).__name__}: {exc}" if not str(exc) else str(exc))
        else:
            self.done.emit(result)

"""Background Qt worker for the Desktop execution boundary."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from .application import (
    DesktopExecutionError,
    DesktopExecutionResult,
    DesktopExecutionService,
)


class DesktopExecutionWorker(QObject):
    log = Signal(str)
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(
        self,
        service: DesktopExecutionService,
        workspace: str,
        request: str,
    ) -> None:
        super().__init__()
        self._service = service
        self._workspace = workspace
        self._request = request

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit("Starting AFDE execution...")
            self.log.emit("Provider: mock")
            result = self._service.execute(self._workspace, self._request)
        except DesktopExecutionError as exc:
            self.failed.emit(exc)
        except Exception as exc:  # keep the Qt event loop alive on worker bugs
            self.failed.emit(
                DesktopExecutionError(
                    "Desktop worker failed.",
                    str(exc),
                    "Review the log and run the bounded Mock task again.",
                    exit_code=5,
                )
            )
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


__all__ = ["DesktopExecutionResult", "DesktopExecutionWorker"]

"""Application bootstrap for AI Factory Desktop."""
from __future__ import annotations

import sys
from typing import Sequence

from PySide6.QtWidgets import QApplication

from .window import DesktopMainWindow


def main(argv: Sequence[str] | None = None) -> int:
    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName("AI Factory Desktop")
    application.setOrganizationName("AI Factory OS")
    window = DesktopMainWindow()
    window.show()
    if not owns_application:
        return 0
    return application.exec()


__all__ = ["main"]

"""Single-window AI Factory Desktop MVP."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .application import (
    DesktopExecutionError,
    DesktopExecutionResult,
    DesktopExecutionService,
    DesktopStatus,
    view_state,
)
from .worker import DesktopExecutionWorker


class DesktopMainWindow(QMainWindow):
    def __init__(self, *, service: DesktopExecutionService | None = None) -> None:
        super().__init__()
        self._service = service or DesktopExecutionService()
        self._thread: QThread | None = None
        self._worker: DesktopExecutionWorker | None = None
        self._last_evidence: Path | None = None

        self.setWindowTitle("AI Factory Desktop")
        self.resize(900, 650)
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._apply_state(DesktopStatus.IDLE)

    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("AI Factory Desktop")
        title.setObjectName("desktopTitle")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        subtitle = QLabel("Powered by AI Factory OS  •  Beta")
        subtitle.setStyleSheet("color: #60646c;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(QLabel("Project Workspace"))
        workspace_row = QHBoxLayout()
        self.workspace_input = QLineEdit()
        self.workspace_input.setPlaceholderText(
            r"C:\AIFactory\Projects\ai_sns_automation_system"
        )
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_workspace)
        workspace_row.addWidget(self.workspace_input, 1)
        workspace_row.addWidget(self.browse_button)
        layout.addLayout(workspace_row)

        layout.addWidget(QLabel("Goal"))
        self.request_input = QTextEdit()
        self.request_input.setPlaceholderText(
            "ASAS 저장소의 현재 상태를 읽기 전용으로 분석하고 "
            "다음 Sprint 준비 상태를 평가해줘."
        )
        self.request_input.setMinimumHeight(100)
        layout.addWidget(self.request_input)

        control_row = QHBoxLayout()
        self.run_button = QPushButton("Run")
        self.clear_button = QPushButton("Clear Log")
        self.open_evidence_button = QPushButton("Open Evidence")
        self.run_button.clicked.connect(self._run)
        self.clear_button.clicked.connect(self._clear_log)
        self.open_evidence_button.clicked.connect(self._open_evidence)
        control_row.addWidget(self.run_button)
        control_row.addWidget(self.clear_button)
        control_row.addStretch(1)
        control_row.addWidget(self.open_evidence_button)
        layout.addLayout(control_row)

        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self.status_label = QLabel()
        self.status_label.setObjectName("desktopStatus")
        self.status_label.setStyleSheet("font-weight: 600;")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("Execution Log"))
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(190)
        layout.addWidget(self.log_output, 1)

        self.setCentralWidget(central)

    @Slot()
    def _browse_workspace(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Select Project Workspace", self.workspace_input.text() or "",
        )
        if selected:
            self.workspace_input.setText(str(Path(selected).resolve()))

    @Slot()
    def _clear_log(self) -> None:
        self.log_output.clear()

    @Slot()
    def _run(self) -> None:
        self._last_evidence = None
        self._apply_state(DesktopStatus.VALIDATING)
        self._append_log("Validating workspace...")
        try:
            request = self._service.validate(
                self.workspace_input.text(), self.request_input.toPlainText(),
            )
        except DesktopExecutionError as exc:
            self._show_failure(exc)
            return

        self.workspace_input.setText(str(request.workspace))
        self._apply_state(DesktopStatus.RUNNING)
        thread = QThread(self)
        worker = DesktopExecutionWorker(
            self._service, str(request.workspace), request.request,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.succeeded.connect(self._show_success)
        worker.failed.connect(self._show_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _show_success(self, result: DesktopExecutionResult) -> None:
        self._last_evidence = result.evidence_path
        for line in (
            f"Session created: {result.session_id}",
            f"Status: {result.status}",
            f"Provider: {result.provider}",
            f"Execution mode: {result.execution_mode}",
            f"Evidence: {result.evidence_path}",
            f"Exit code: {result.exit_code}",
            "Execution completed.",
        ):
            self._append_log(line)
        self._apply_state(DesktopStatus.COMPLETED, evidence_available=True)

    @Slot(object)
    def _show_failure(self, error: DesktopExecutionError) -> None:
        for line in error.log_lines():
            self._append_log(line)
        self._apply_state(DesktopStatus.FAILED)

    @Slot()
    def _thread_finished(self) -> None:
        self._worker = None
        self._thread = None

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(str(message))
        bar = self.log_output.verticalScrollBar()
        bar.setValue(bar.maximum())

    @Slot()
    def _open_evidence(self) -> None:
        if self._last_evidence is None:
            self._append_log("Evidence file is not available.")
            return
        try:
            self._service.open_evidence(self._last_evidence)
        except DesktopExecutionError as exc:
            for line in exc.log_lines()[1:]:
                self._append_log(line)

    def _apply_state(
        self, status: DesktopStatus, *, evidence_available: bool = False,
    ) -> None:
        state = view_state(status, evidence_available=evidence_available)
        self.status_label.setText(state.status.value)
        self.workspace_input.setEnabled(state.inputs_enabled)
        self.browse_button.setEnabled(state.inputs_enabled)
        self.request_input.setEnabled(state.inputs_enabled)
        self.run_button.setEnabled(state.run_enabled)
        self.open_evidence_button.setEnabled(state.open_evidence_enabled)
        if state.progress_active:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(
                1 if status is DesktopStatus.COMPLETED else 0
            )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(
                self,
                "Execution in progress",
                "AFDE execution is still running. Wait for completion before closing.",
            )
            event.ignore()
            return
        event.accept()


__all__ = ["DesktopMainWindow"]

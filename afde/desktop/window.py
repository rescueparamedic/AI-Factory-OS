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


_STATUS_DISPLAY = {
    DesktopStatus.IDLE: "대기 중",
    DesktopStatus.VALIDATING: "입력 확인 중",
    DesktopStatus.RUNNING: "AI 작업 실행 중",
    DesktopStatus.COMPLETED: "실행 완료",
    DesktopStatus.FAILED: "실행 실패",
}


class DesktopMainWindow(QMainWindow):
    def __init__(self, *, service: DesktopExecutionService | None = None) -> None:
        super().__init__()
        self._service = service or DesktopExecutionService()
        self._thread: QThread | None = None
        self._worker: DesktopExecutionWorker | None = None
        self._last_evidence: Path | None = None
        self._status = DesktopStatus.IDLE

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

        self.workspace_label = QLabel("1. 프로젝트 폴더")
        self.workspace_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.workspace_label)
        workspace_row = QHBoxLayout()
        self.workspace_input = QLineEdit()
        self.workspace_input.setPlaceholderText(
            r"C:\AIFactory\Projects\ai_sns_automation_system"
        )
        self.browse_button = QPushButton("폴더 선택")
        self.browse_button.clicked.connect(self._browse_workspace)
        workspace_row.addWidget(self.workspace_input, 1)
        workspace_row.addWidget(self.browse_button)
        layout.addLayout(workspace_row)

        self.request_label = QLabel("2. AI에게 맡길 작업")
        self.request_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.request_label)
        self.request_input = QTextEdit()
        self.request_input.setPlaceholderText(
            "예: 이 프로젝트의 현재 상태를 분석하고 다음 Sprint 준비 항목을 "
            "정리해 주세요."
        )
        self.request_input.setMinimumHeight(100)
        layout.addWidget(self.request_input)

        control_row = QHBoxLayout()
        self.run_button = QPushButton("3. AI 실행")
        self.run_button.setMinimumHeight(44)
        self.run_button.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border: 0; "
            "border-radius: 4px; padding: 8px 20px; font-size: 16px; "
            "font-weight: 600; } "
            "QPushButton:hover { background: #1d4ed8; } "
            "QPushButton:disabled { background: #aeb8c8; color: #f8fafc; }"
        )
        self.clear_button = QPushButton("기록 지우기")
        self.open_evidence_button = QPushButton("실행 결과 열기")
        self.open_evidence_button.setMinimumHeight(36)
        self.run_button.clicked.connect(self._run)
        self.clear_button.clicked.connect(self._clear_log)
        self.open_evidence_button.clicked.connect(self._open_evidence)
        control_row.addWidget(self.run_button, 1)
        control_row.addWidget(self.clear_button)
        control_row.addWidget(self.open_evidence_button)
        layout.addLayout(control_row)

        status_row = QHBoxLayout()
        self.status_title_label = QLabel("현재 상태")
        status_row.addWidget(self.status_title_label)
        self.status_label = QLabel()
        self.status_label.setObjectName("desktopStatus")
        self.status_label.setStyleSheet("font-weight: 600;")
        status_row.addWidget(self.status_label)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName("진행 상태")
        layout.addWidget(self.progress)

        self.log_title_label = QLabel("상세 실행 기록")
        self.log_title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.log_title_label)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(190)
        layout.addWidget(self.log_output, 1)

        self.workspace_input.textChanged.connect(self._refresh_run_button)
        self.request_input.textChanged.connect(self._refresh_run_button)

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
        if self._thread is not None and self._thread.isRunning():
            self._append_log("Execution is already running.")
            return
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
        self._refresh_run_button()

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
        self._status = status
        state = view_state(status, evidence_available=evidence_available)
        self.status_label.setText(_STATUS_DISPLAY[state.status])
        self.workspace_input.setEnabled(state.inputs_enabled)
        self.browse_button.setEnabled(state.inputs_enabled)
        self.request_input.setEnabled(state.inputs_enabled)
        self.open_evidence_button.setEnabled(state.open_evidence_enabled)
        self._refresh_run_button()
        if state.progress_active:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(
                1 if status is DesktopStatus.COMPLETED else 0
            )

    def _refresh_run_button(self, *_args: object) -> None:
        state = view_state(self._status)
        inputs_ready = bool(
            self.workspace_input.text().strip()
            and self.request_input.toPlainText().strip()
        )
        thread_active = self._thread is not None and self._thread.isRunning()
        self.run_button.setEnabled(
            state.run_enabled and inputs_ready and not thread_active
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

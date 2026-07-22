import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from afde.desktop.application import DesktopExecutionResult, DesktopStatus
from afde.desktop.window import DesktopMainWindow


@pytest.fixture(scope="module")
def qt_application():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def window(qt_application):
    main_window = DesktopMainWindow()
    yield main_window
    main_window.close()
    main_window.deleteLater()
    qt_application.processEvents()


def test_operator_labels_show_three_step_korean_flow(window):
    assert window.workspace_label.text() == "1. 프로젝트 폴더"
    assert window.browse_button.text() == "폴더 선택"
    assert window.request_label.text() == "2. AI에게 맡길 작업"
    assert window.run_button.text() == "3. AI 실행"
    assert window.clear_button.text() == "기록 지우기"
    assert window.open_evidence_button.text() == "실행 결과 열기"
    assert window.status_title_label.text() == "현재 상태"
    assert window.log_title_label.text() == "상세 실행 기록"


@pytest.mark.parametrize(
    ("status", "display"),
    [
        (DesktopStatus.IDLE, "대기 중"),
        (DesktopStatus.VALIDATING, "입력 확인 중"),
        (DesktopStatus.RUNNING, "AI 작업 실행 중"),
        (DesktopStatus.COMPLETED, "실행 완료"),
        (DesktopStatus.FAILED, "실행 실패"),
    ],
)
def test_internal_status_is_translated_only_for_display(window, status, display):
    window._apply_state(status)

    assert window.status_label.text() == display
    assert status.value in {"Idle", "Validating", "Running", "Completed", "Failed"}


def test_run_requires_workspace_and_goal_before_validation(window, tmp_path):
    assert not window.run_button.isEnabled()

    window.workspace_input.setText(str(tmp_path))
    assert not window.run_button.isEnabled()

    window.request_input.setPlainText("Review the bounded Mock flow")
    assert window.run_button.isEnabled()

    window.workspace_input.clear()
    assert not window.run_button.isEnabled()


def test_running_disables_inputs_run_and_result_controls(window, tmp_path):
    window.workspace_input.setText(str(tmp_path))
    window.request_input.setPlainText("Review the bounded Mock flow")

    window._apply_state(DesktopStatus.RUNNING)

    assert not window.workspace_input.isEnabled()
    assert not window.browse_button.isEnabled()
    assert not window.request_input.isEnabled()
    assert not window.run_button.isEnabled()
    assert not window.open_evidence_button.isEnabled()
    assert window.progress.minimum() == 0
    assert window.progress.maximum() == 0


def test_completion_enables_result_and_preserves_detailed_log(window, tmp_path):
    evidence = tmp_path / "execution_evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    window.workspace_input.setText(str(tmp_path))
    window.request_input.setPlainText("Review the bounded Mock flow")
    result = DesktopExecutionResult(
        status="completed",
        session_id="RWS-BETA-window",
        provider="mock",
        execution_mode="deterministic_mock",
        evidence_path=Path(evidence),
        exit_code=0,
        payload={},
    )

    window._show_success(result)

    assert window.status_label.text() == "실행 완료"
    assert window.run_button.isEnabled()
    assert window.open_evidence_button.isEnabled()
    assert window.progress.value() == 1
    log = window.log_output.toPlainText()
    assert "Session created: RWS-BETA-window" in log
    assert "Provider: mock" in log
    assert f"Evidence: {evidence}" in log
    assert "Exit code: 0" in log

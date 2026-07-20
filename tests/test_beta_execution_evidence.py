import json
from pathlib import Path
import subprocess
import sys

import pytest

from afde.cli import main
from afde.execution.bridge import ProviderRuntimeBridge


def _execute(tmp_path, capsys, monkeypatch=None, *, failed=False):
    if failed:
        def fail_bridge(*args, **kwargs):
            raise RuntimeError('bounded Evidence failure')

        monkeypatch.setattr(ProviderRuntimeBridge, 'convert', fail_bridge)
    code = main([
        'execute', '--request', 'Inspect persisted Beta Evidence',
        '--workspace', str(tmp_path), '--json',
    ])
    result = json.loads(capsys.readouterr().out)
    return code, result


def _evidence_path(tmp_path, result):
    return tmp_path / result['evidence_path']


def _inspect(tmp_path, session_id, capsys, *, json_output=False):
    argv = [
        'execution-evidence', '--session-id', session_id,
        '--workspace', str(tmp_path),
    ]
    if json_output:
        argv.append('--json')
    code = main(argv)
    return code, capsys.readouterr().out


def test_completed_evidence_has_operator_human_summary(tmp_path, capsys):
    execute_code, result = _execute(tmp_path, capsys)

    code, output = _inspect(tmp_path, result['session_id'], capsys)

    assert execute_code == code == 0
    assert f"Execution ID: {result['execution_id']}" in output
    assert f"Session ID: {result['session_id']}" in output
    assert 'Status: completed' in output
    assert 'Stage: completed' in output
    assert 'Provider: mock' in output
    assert 'Execution mode: deterministic' in output
    assert 'Duration:' in output
    assert 'Error code: none' in output
    assert output.endswith('execution_evidence.json\n')


def test_failed_evidence_has_operator_error_summary(
    tmp_path, capsys, monkeypatch,
):
    execute_code, result = _execute(
        tmp_path, capsys, monkeypatch, failed=True,
    )

    code, output = _inspect(tmp_path, result['session_id'], capsys)

    assert execute_code == 5
    assert code == 0
    assert 'Status: failed' in output
    assert 'Stage: bridge' in output
    assert 'Error code: BETA_BRIDGE_CONVERSION' in output
    assert 'Error category: bridge_conversion' in output
    assert 'Error retryable: false' in output


@pytest.mark.parametrize('failed', [False, True])
def test_json_returns_sanitized_persisted_structure_without_envelope(
    tmp_path, capsys, monkeypatch, failed,
):
    _, result = _execute(tmp_path, capsys, monkeypatch, failed=failed)
    path = _evidence_path(tmp_path, result)
    persisted = json.loads(path.read_text(encoding='utf-8'))

    code, output = _inspect(
        tmp_path, result['session_id'], capsys, json_output=True,
    )
    inspected = json.loads(output)

    assert code == 0
    assert inspected == persisted
    assert 'evidence' not in inspected
    assert inspected['execution_status'] in {'completed', 'failed'}


@pytest.mark.parametrize(
    'session_id',
    ['', '../escape', 'nested/session', r'C:\absolute\session'],
)
def test_invalid_session_ids_return_input_exit_code(
    tmp_path, capsys, session_id,
):
    code, output = _inspect(
        tmp_path, session_id, capsys, json_output=True,
    )
    failure = json.loads(output)

    assert code == 2
    assert failure['status'] == 'failed'
    assert failure['evidence'] == 'unavailable'
    assert 'execution-evidence --help' in failure['next_action']


def test_missing_evidence_returns_not_found_exit_code(tmp_path, capsys):
    code, output = _inspect(
        tmp_path, 'RWS-BETA-missing', capsys, json_output=True,
    )
    failure = json.loads(output)

    assert code == 4
    assert 'was not found' in failure['error']
    assert failure['evidence'].endswith('execution_evidence.json')


@pytest.mark.parametrize('contents', ['{broken', '[]'])
def test_corrupt_or_structurally_invalid_evidence_returns_five(
    tmp_path, capsys, contents,
):
    session_id = 'RWS-BETA-corrupt'
    path = (
        tmp_path / 'data' / 'runtime_sessions' / session_id
        / 'execution_evidence.json'
    )
    path.parent.mkdir(parents=True)
    path.write_text(contents, encoding='utf-8')

    code, output = _inspect(
        tmp_path, session_id, capsys, json_output=True,
    )

    assert code == 5
    assert 'could not be read' in json.loads(output)['error']


def test_unreadable_evidence_returns_five(tmp_path, capsys, monkeypatch):
    _, result = _execute(tmp_path, capsys)
    target = _evidence_path(tmp_path, result).resolve()
    original = Path.read_bytes

    def deny_read(path):
        if path.resolve() == target:
            raise PermissionError('test denied Evidence read')
        return original(path)

    monkeypatch.setattr(Path, 'read_bytes', deny_read)
    code, output = _inspect(
        tmp_path, result['session_id'], capsys, json_output=True,
    )

    assert code == 5
    assert 'unreadable' in json.loads(output)['cause']


def test_read_is_byte_preserving_and_defensively_redacts_output(
    tmp_path, capsys,
):
    session_id = 'RWS-BETA-sensitive'
    secret = 'sk-test-secret-value'
    value = {
        'session_id': session_id,
        'execution_status': 'failed',
        'error': {
            'message': f'Authorization: Bearer {secret}',
            'api_key': secret,
        },
        'security': {'credentials_persisted': False},
    }
    path = (
        tmp_path / 'data' / 'runtime_sessions' / session_id
        / 'execution_evidence.json'
    )
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value), encoding='utf-8')
    before = path.read_bytes()

    code, output = _inspect(
        tmp_path, session_id, capsys, json_output=True,
    )

    assert code == 0
    assert secret not in output
    assert output.count('[REDACTED]') == 2
    assert json.loads(output)['security']['credentials_persisted'] is False
    assert path.read_bytes() == before


def test_internal_session_mismatch_is_rejected(tmp_path, capsys):
    session_id = 'RWS-BETA-requested'
    path = (
        tmp_path / 'data' / 'runtime_sessions' / session_id
        / 'execution_evidence.json'
    )
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({'session_id': 'RWS-BETA-other'}), encoding='utf-8',
    )

    code, _ = _inspect(tmp_path, session_id, capsys, json_output=True)

    assert code == 5


def test_linked_session_directory_is_rejected(tmp_path, capsys):
    session_id = 'RWS-BETA-linked'
    outside = tmp_path.parent / f'{tmp_path.name}-outside-evidence'
    outside.mkdir()
    (outside / 'execution_evidence.json').write_text(
        json.dumps({'session_id': session_id}), encoding='utf-8',
    )
    sessions = tmp_path / 'data' / 'runtime_sessions'
    sessions.mkdir(parents=True)
    try:
        (sessions / session_id).symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'symlink creation unavailable: {exc}')

    code, output = _inspect(
        tmp_path, session_id, capsys, json_output=True,
    )

    assert code == 2
    assert 'containment checks' in json.loads(output)['cause']


def test_failed_execute_next_action_names_a_working_command(
    tmp_path, capsys, monkeypatch,
):
    execute_code, result = _execute(
        tmp_path, capsys, monkeypatch, failed=True,
    )

    assert execute_code == 5
    assert 'python -m afde.cli execution-evidence' in result['next_action']
    assert 'runtime-history' not in result['next_action']
    completed = subprocess.run(
        [
            sys.executable, '-m', 'afde.cli', 'execution-evidence',
            '--session-id', result['session_id'],
            '--workspace', str(tmp_path), '--json',
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, check=False,
    )
    inspected = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert inspected['session_id'] == result['session_id']

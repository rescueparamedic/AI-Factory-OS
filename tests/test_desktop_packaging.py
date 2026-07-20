from pathlib import Path

from afde.desktop.application import DesktopExecutionService
from afde.desktop.packaging import (
    APPLICATION_NAME,
    expected_executable_path,
    resource_root,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'packaging' / 'ai_factory_desktop.spec'
BUILD_SCRIPT = ROOT / 'scripts' / 'build_desktop_exe.ps1'
ENTRY_POINT = ROOT / 'packaging' / 'desktop_entry.py'


def test_packaging_contract_files_exist():
    assert SPEC.is_file()
    assert BUILD_SCRIPT.is_file()
    assert ENTRY_POINT.is_file()
    assert (ROOT / 'requirements-packaging.txt').is_file()


def test_spec_is_windowed_onedir_without_user_data():
    content = SPEC.read_text(encoding='utf-8')

    assert 'AI Factory Desktop' in content
    assert 'console=False' in content
    assert 'COLLECT(' in content
    assert 'datas=[]' in content
    assert 'afde.cli' in content
    for forbidden in ('.env', 'runtime_sessions', 'execution_evidence.json'):
        assert forbidden not in content


def test_build_script_has_bounded_cleanup_and_expected_output():
    content = BUILD_SCRIPT.read_text(encoding='utf-8')

    assert 'Remove-RepositoryBuildDirectory' in content
    assert 'Refusing to remove a path outside the repository' in content
    assert 'ai_factory_desktop.spec' in content
    assert 'AI Factory Desktop\\AI Factory Desktop.exe' in content


def test_expected_executable_path_is_stable(tmp_path):
    expected = expected_executable_path(tmp_path)

    assert expected == (
        tmp_path.resolve()
        / 'dist'
        / APPLICATION_NAME
        / f'{APPLICATION_NAME}.exe'
    )


def test_resource_root_supports_source_and_frozen_modes(tmp_path):
    class SourceRuntime:
        frozen = False

    class FrozenRuntime:
        frozen = True
        _MEIPASS = str(tmp_path)
        executable = str(tmp_path / 'AI Factory Desktop.exe')

    assert resource_root(SourceRuntime).is_dir()
    assert resource_root(FrozenRuntime) == tmp_path.resolve()


def test_frozen_service_reuses_cli_contract_and_restores_environment(
    tmp_path, monkeypatch,
):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-must-be-restored')
    monkeypatch.setenv('AI_FACTORY_RUN_LIVE_OPENAI_TESTS', '1')

    def forbidden_runner(*args, **kwargs):
        raise AssertionError('frozen execution must not launch python -m')

    result = DesktopExecutionService(
        runner=forbidden_runner, frozen=True,
    ).execute(str(tmp_path), 'Create one packaged Desktop result')

    assert result.status == 'completed'
    assert result.provider == 'mock'
    assert result.evidence_path.is_file()
    assert __import__('os').environ['OPENAI_API_KEY'] == 'sk-must-be-restored'
    assert __import__('os').environ['AI_FACTORY_RUN_LIVE_OPENAI_TESTS'] == '1'


def test_desktop_entry_import_is_side_effect_free():
    namespace = {'__name__': 'packaging_probe'}
    source = ENTRY_POINT.read_text(encoding='utf-8')

    exec(compile(source, str(ENTRY_POINT), 'exec'), namespace)

    assert callable(namespace['main'])

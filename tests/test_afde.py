from pathlib import Path

from afde.task_runner import AFDETaskRunner
from afde.provider_manager import ProviderManager
from afde.git_manager import GitManager


def test_afde_mock_pipeline(tmp_path: Path):
    runner = AFDETaskRunner(tmp_path)
    result = runner.run_mock_pipeline("AFDE test", "Create a test artifact")
    assert result.status == "success"
    assert Path(result.artifact_path).exists()
    assert result.workspace_id


def test_provider_manager_has_mock(tmp_path: Path):
    providers = ProviderManager(tmp_path).as_dicts()
    assert any(item["provider"] == "mock" and item["configured"] for item in providers)


def test_git_manager_prepare_commit_commands(tmp_path: Path):
    commands = GitManager(tmp_path).prepare_commit_commands("Sprint-AFDE-1")
    assert commands[0] == "git add ."
    assert 'git commit -m "Sprint-AFDE-1"' in commands
    assert commands[-1] == "git push"

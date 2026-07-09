"""AI Factory Development Environment (AFDE).

AFDE is the local development workspace layer for AI Factory OS.
It manages sprint tasks, workspace folders, artifacts, prompt templates,
provider metadata, and safe Git command preparation.
"""

from .workspace_manager import WorkspaceManager
from .artifact_manager import ArtifactManager
from .task_runner import AFDETaskRunner
from .git_manager import GitManager
from .prompt_manager import PromptManager
from .provider_manager import ProviderManager

__all__ = [
    "WorkspaceManager",
    "ArtifactManager",
    "AFDETaskRunner",
    "GitManager",
    "PromptManager",
    "ProviderManager",
]

"""Immutable contracts for governed, non-executable Production Action Planning."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import re

from real_worker_runtime.tool_actions import (
    ToolAction,
    ToolActionType,
    ToolActionValidationError,
)

from .errors import (
    InvalidProductionActionPlanningRequestError,
    InvalidProductionActionProposalError,
    UnsafeProductionFileReadTargetError,
)


MAX_REQUEST_CHARACTERS = 1000
MAX_FILE_READ_BYTES = 65536
CAPABILITY_ID = "CAP-TOOLADAPTER-CONTRACT-0001"
WORKER_ID = "development_worker"
RUNTIME_PROVIDER = "codex_automation_bridge"
RUNTIME_MODEL = "controlled-runtime"
EXECUTION_MODE = "production_adapter_runtime"
PLANNING_STAGE = "production_action_planning"

_ALLOWED_PLAN_ACTION_TYPES = frozenset({
    ToolActionType.FILE_READ,
    ToolActionType.GIT_STATUS,
    ToolActionType.GIT_DIFF,
})
_CREDENTIAL_NAMES = frozenset({
    ".env", "credentials.json", "id_rsa", "id_ed25519",
})
_CREDENTIAL_SUFFIXES = frozenset({".pem", ".key", ".pfx", ".p12"})
_ACTION_ID_PATTERN = re.compile(r"PROD-ACTION-[A-Za-z0-9._-]+")
_TASK_ID_PATTERN = re.compile(r"TASK-PRODACTION-[A-Za-z0-9._-]+")
_SESSION_ID_PATTERN = re.compile(r"production-action-[A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ProductionActionPlanningRequest:
    """Ordinary caller inputs with no execution identity or credential fields."""

    workspace: Path
    request: str

    def __post_init__(self) -> None:
        try:
            workspace = Path(self.workspace).expanduser().resolve(strict=True)
        except (OSError, TypeError, ValueError) as exc:
            raise InvalidProductionActionPlanningRequestError(
                "workspace must be an existing directory"
            ) from exc
        if not workspace.is_dir():
            raise InvalidProductionActionPlanningRequestError(
                "workspace must be an existing directory"
            )
        if not isinstance(self.request, str):
            raise InvalidProductionActionPlanningRequestError(
                "request must be a string"
            )
        request = self.request.strip()
        if not request:
            raise InvalidProductionActionPlanningRequestError(
                "request must not be empty"
            )
        if len(request) > MAX_REQUEST_CHARACTERS:
            raise InvalidProductionActionPlanningRequestError(
                "request must not exceed 1000 characters"
            )
        object.__setattr__(self, "workspace", workspace)
        object.__setattr__(self, "request", request)


@dataclass(frozen=True, init=False)
class ProductionActionPlan:
    """Sealed result produced only by the trusted planning boundary."""

    capability_id: str
    task_id: str
    worker_id: str
    runtime_session_id: str
    runtime_provider: str
    runtime_model: str
    execution_mode: str
    planning_provider: str
    planning_model: str
    tool_action: ToolAction
    runtime_allowed: bool = False
    execution_allowed: bool = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise InvalidProductionActionProposalError(
            "ProductionActionPlan is a result-only contract; use "
            "ProductionActionPlanner.plan()"
        )


def _build_production_action_plan(
    *,
    workspace: Path,
    trusted_branch: str,
    task_id: str,
    runtime_session_id: str,
    planning_provider: str,
    planning_model: str,
    tool_action: ToolAction,
) -> ProductionActionPlan:
    """Validate all trusted relationships before creating the sealed result."""

    trusted_workspace = _exact_workspace(workspace)
    if (
        not isinstance(trusted_branch, str)
        or not trusted_branch
        or trusted_branch != trusted_branch.strip()
    ):
        raise InvalidProductionActionProposalError(
            "trusted branch must be an exact non-empty string"
        )
    if not isinstance(task_id, str) or not _TASK_ID_PATTERN.fullmatch(task_id):
        raise InvalidProductionActionProposalError(
            "plan task identity violates system policy"
        )
    if (
        not isinstance(runtime_session_id, str)
        or not _SESSION_ID_PATTERN.fullmatch(runtime_session_id)
    ):
        raise InvalidProductionActionProposalError(
            "plan session identity violates system policy"
        )
    for value in (planning_provider, planning_model):
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
        ):
            raise InvalidProductionActionProposalError(
                "planning provenance must use exact non-empty strings"
            )
    if type(tool_action) is not ToolAction:
        raise InvalidProductionActionProposalError(
            "plan must contain exactly one existing ToolAction"
        )
    try:
        canonical_action = ToolAction.from_value(tool_action.to_dict())
    except (ToolActionValidationError, TypeError, ValueError):
        raise InvalidProductionActionProposalError(
            "plan ToolAction failed canonical validation"
        ) from None

    expected_workspace = str(trusted_workspace)
    expected_metadata = {
        "capability_id": CAPABILITY_ID,
        "planning_provider": planning_provider,
        "planning_model": planning_model,
    }
    checks = (
        (canonical_action.cwd == expected_workspace, "cwd"),
        (canonical_action.repository == expected_workspace, "repository"),
        (canonical_action.branch == trusted_branch, "branch"),
        (bool(_ACTION_ID_PATTERN.fullmatch(canonical_action.action_id)), "action_id"),
        (canonical_action.runtime_task_id == task_id, "runtime_task_id"),
        (
            canonical_action.runtime_session_id == runtime_session_id,
            "runtime_session_id",
        ),
        (canonical_action.source_worker == WORKER_ID, "source_worker"),
        (canonical_action.stage == PLANNING_STAGE, "stage"),
        (canonical_action.revision == 1, "revision"),
        (canonical_action.action_type in _ALLOWED_PLAN_ACTION_TYPES, "action_type"),
        (canonical_action.arguments == {}, "arguments"),
        (canonical_action.preconditions == {}, "preconditions"),
        (canonical_action.expected_result == {}, "expected_result"),
        (canonical_action.metadata == expected_metadata, "metadata"),
    )
    for accepted, field_name in checks:
        if not accepted:
            raise InvalidProductionActionProposalError(
                f"plan ToolAction {field_name} conflicts with trusted context"
            )

    if canonical_action.action_type is ToolActionType.FILE_READ:
        normalized_target = _validate_file_read_target(
            trusted_workspace, canonical_action.target,
        )
        if canonical_action.target != normalized_target:
            raise InvalidProductionActionProposalError(
                "plan FILE_READ target is not normalized"
            )
    elif canonical_action.target != "":
        raise InvalidProductionActionProposalError(
            "plan Git ToolAction must use an empty target"
        )

    protected_mapping = canonical_action.to_dict()
    for field_name in (
        "arguments", "preconditions", "expected_result", "metadata",
    ):
        protected_mapping[field_name] = _ImmutableDict(
            protected_mapping[field_name]
        )
    try:
        canonical_action = ToolAction.from_value(protected_mapping)
    except ToolActionValidationError:
        raise InvalidProductionActionProposalError(
            "plan ToolAction failed protected canonical validation"
        ) from None

    result = object.__new__(ProductionActionPlan)
    values = {
        "capability_id": CAPABILITY_ID,
        "task_id": task_id,
        "worker_id": WORKER_ID,
        "runtime_session_id": runtime_session_id,
        "runtime_provider": RUNTIME_PROVIDER,
        "runtime_model": RUNTIME_MODEL,
        "execution_mode": EXECUTION_MODE,
        "planning_provider": planning_provider,
        "planning_model": planning_model,
        "tool_action": canonical_action,
        "runtime_allowed": False,
        "execution_allowed": False,
    }
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _exact_workspace(workspace: object) -> Path:
    if not isinstance(workspace, Path):
        raise InvalidProductionActionProposalError(
            "trusted workspace must be an exact resolved Path"
        )
    try:
        resolved = workspace.resolve(strict=True)
    except OSError:
        raise InvalidProductionActionProposalError(
            "trusted workspace must be an existing directory"
        ) from None
    if not resolved.is_dir() or workspace != resolved:
        raise InvalidProductionActionProposalError(
            "trusted workspace must be the exact resolved planning workspace"
        )
    return resolved


def _validate_file_read_target(workspace: Path, raw: object) -> str:
    """Apply the governed read policy without reading file contents."""

    if not isinstance(raw, str):
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ target must be a safe relative workspace path"
        )
    candidate = Path(raw)
    windows_candidate = PureWindowsPath(raw)
    if (
        not raw
        or raw != raw.strip()
        or candidate.is_absolute()
        or windows_candidate.is_absolute()
        or ".." in candidate.parts
        or ".." in windows_candidate.parts
    ):
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ target must be a safe relative workspace path"
        )
    try:
        target = (workspace / candidate).resolve(strict=True)
        relative = target.relative_to(workspace)
    except (OSError, ValueError):
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ target is missing or outside the governed workspace"
        ) from None
    lowered_parts = {part.lower() for part in relative.parts}
    if ".git" in lowered_parts:
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ cannot target Git metadata"
        )
    if (
        target.name.lower() in _CREDENTIAL_NAMES
        or target.suffix.lower() in _CREDENTIAL_SUFFIXES
    ):
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ cannot target credential-like files"
        )
    try:
        valid_file = target.is_file()
        size = target.stat().st_size
    except OSError:
        valid_file = False
        size = 0
    if not valid_file or size > MAX_FILE_READ_BYTES:
        raise UnsafeProductionFileReadTargetError(
            "FILE_READ target must be a regular file within the 64 KiB bound"
        )
    return relative.as_posix()


class _ImmutableDict(dict):
    """A dict-compatible immutable snapshot for existing ToolAction fields."""

    def __init__(self, value: dict[object, object]) -> None:
        dict.__init__(self, value)

    def _deny(self, *args: object, **kwargs: object) -> None:
        raise TypeError("governed ToolAction mappings are immutable")

    __delitem__ = _deny
    __ior__ = _deny
    __setitem__ = _deny
    clear = _deny
    pop = _deny
    popitem = _deny
    setdefault = _deny
    update = _deny

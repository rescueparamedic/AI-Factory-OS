"""One-shot governed Production Action Planning application boundary."""
from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from afde.git_manager import GitManager
from afde.providers import (
    AIProvider,
    AIProviderError,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponse,
    ProviderResponseError,
    create_provider,
)
from real_worker_runtime.tool_actions import (
    ToolAction,
    ToolActionType,
    ToolActionValidationError,
)

from .errors import (
    InvalidProductionActionPlanningRequestError,
    InvalidProductionActionProposalError,
    ProductionActionPlanningGitContextError,
    ProductionActionPlanningProviderConfigurationError,
    ProductionActionPlanningProviderRequestError,
    ProductionToolActionValidationError,
    UnsupportedProductionActionTypeError,
)
from .models import (
    CAPABILITY_ID,
    PLANNING_STAGE,
    WORKER_ID,
    ProductionActionPlan,
    ProductionActionPlanningRequest,
    _build_production_action_plan,
    _validate_file_read_target,
)


_ALLOWED_ACTION_TYPES = frozenset({"FILE_READ", "GIT_STATUS", "GIT_DIFF"})
_PROPOSAL_KEYS = frozenset({"action_type", "purpose", "target"})


class ProductionActionPlanner:
    """Plan one read-only ToolAction without invoking any execution boundary."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        task_id_factory: Callable[[], str] | None = None,
        action_id_factory: Callable[[], str] | None = None,
        session_id_factory: Callable[[], str] | None = None,
        git_manager_factory: Callable[[Path], GitManager] = GitManager,
    ) -> None:
        if not isinstance(provider, AIProvider):
            raise ProductionActionPlanningProviderConfigurationError(
                "provider must implement the existing AIProvider contract"
            )
        self._provider = provider
        self._task_id_factory = task_id_factory or _task_id
        self._action_id_factory = action_id_factory or _action_id
        self._session_id_factory = session_id_factory or _session_id
        self._git_manager_factory = git_manager_factory

    def plan(
        self,
        planning_request: ProductionActionPlanningRequest,
    ) -> ProductionActionPlan:
        """Perform exactly one provider call and return one inert action plan."""

        if type(planning_request) is not ProductionActionPlanningRequest:
            raise InvalidProductionActionPlanningRequestError(
                "planning_request must be ProductionActionPlanningRequest"
            )
        workspace = planning_request.workspace
        branch = self._trusted_branch(workspace)
        response = self._generate(_planning_prompt(planning_request.request))
        proposal = _parse_proposal(response.content)
        target = _trusted_target(workspace, proposal)
        task_id = self._identity(
            self._task_id_factory, r"TASK-PRODACTION-[A-Za-z0-9._-]+",
        )
        action_id = self._identity(
            self._action_id_factory, r"PROD-ACTION-[A-Za-z0-9._-]+",
        )
        session_id = self._identity(
            self._session_id_factory, r"production-action-[A-Za-z0-9._-]+",
        )
        mapping = {
            "action_id": action_id,
            "action_type": proposal["action_type"],
            "source_worker": WORKER_ID,
            "purpose": proposal["purpose"],
            "target": target,
            "arguments": {},
            "cwd": str(workspace),
            "repository": str(workspace),
            "branch": branch,
            "runtime_task_id": task_id,
            "runtime_session_id": session_id,
            "stage": PLANNING_STAGE,
            "revision": 1,
            "preconditions": {},
            "expected_result": {},
            "metadata": {
                "capability_id": CAPABILITY_ID,
                "planning_provider": response.provider,
                "planning_model": response.model,
            },
        }
        try:
            tool_action = ToolAction.from_value(mapping)
        except ToolActionValidationError:
            raise ProductionToolActionValidationError(
                "system-hydrated ToolAction failed canonical validation"
            ) from None
        return _build_production_action_plan(
            workspace=workspace,
            trusted_branch=branch,
            task_id=task_id,
            runtime_session_id=session_id,
            planning_provider=response.provider,
            planning_model=response.model,
            tool_action=tool_action,
        )

    @staticmethod
    def _identity(factory: Callable[[], str], pattern: str) -> str:
        try:
            value = factory()
        except Exception:
            raise ProductionToolActionValidationError(
                "system identity generation failed"
            ) from None
        if not isinstance(value, str) or not re.fullmatch(pattern, value):
            raise ProductionToolActionValidationError(
                "system identity generation produced an unsafe identity"
            )
        return value

    def _trusted_branch(self, workspace: Path) -> str:
        try:
            manager = self._git_manager_factory(workspace)
            if manager.status().returncode != 0:
                raise ProductionActionPlanningGitContextError(
                    "workspace must be a Git worktree"
                )
            branch = manager.current_branch()
        except ProductionActionPlanningGitContextError:
            raise
        except (OSError, RuntimeError):
            raise ProductionActionPlanningGitContextError(
                "Git context is unavailable"
            ) from None
        if not isinstance(branch, str) or not branch.strip():
            raise ProductionActionPlanningGitContextError(
                "workspace must have a non-detached current branch"
            )
        return branch.strip()

    def _generate(self, prompt: str) -> ProviderResponse:
        try:
            response = self._provider.generate(prompt)
        except ProviderConfigurationError:
            raise ProductionActionPlanningProviderConfigurationError(
                "planning provider is not configured"
            ) from None
        except ProviderRequestError:
            raise ProductionActionPlanningProviderRequestError(
                "planning provider request failed"
            ) from None
        except ProviderResponseError:
            raise InvalidProductionActionProposalError(
                "planning provider returned an invalid response"
            ) from None
        except AIProviderError:
            raise ProductionActionPlanningProviderRequestError(
                "planning provider request failed"
            ) from None
        if type(response) is not ProviderResponse:
            raise InvalidProductionActionProposalError(
                "planning provider must return ProviderResponse"
            )
        if (
            not isinstance(response.provider, str)
            or not response.provider.strip()
            or not isinstance(response.model, str)
            or not response.model.strip()
        ):
            raise InvalidProductionActionProposalError(
                "planning provider identity is invalid"
            )
        return response


def build_openai_production_action_planner(
    *,
    model: str | None = None,
    allow_live_api: bool = False,
    client: Any | None = None,
    task_id_factory: Callable[[], str] | None = None,
    action_id_factory: Callable[[], str] | None = None,
    session_id_factory: Callable[[], str] | None = None,
) -> ProductionActionPlanner:
    """Build the supported OpenAI path while preserving explicit live opt-in."""

    try:
        provider = create_provider(
            "openai",
            model=model,
            allow_live_api=allow_live_api,
            client=client,
        )
    except ProviderConfigurationError:
        raise ProductionActionPlanningProviderConfigurationError(
            "OpenAI planning provider is not configured or live use is not enabled"
        ) from None
    return ProductionActionPlanner(
        provider,
        task_id_factory=task_id_factory,
        action_id_factory=action_id_factory,
        session_id_factory=session_id_factory,
    )


def _planning_prompt(user_request: str) -> str:
    encoded_request = json.dumps(user_request, ensure_ascii=False)
    return (
        "You are a governed read-only Production Action Planning component. "
        "Return exactly one JSON object and nothing else. The object must have "
        "exactly these keys: action_type, purpose, target. action_type must be "
        "exactly one of FILE_READ, GIT_STATUS, GIT_DIFF. purpose must be a short "
        "bounded reason. target must be one relative workspace file path for "
        "FILE_READ and must be an empty string for Git actions. Prohibited: "
        "FILE_WRITE, COMMAND_RUN, TEST_RUN, GIT_ADD, GIT_COMMIT, "
        "GIT_PUSH_FEATURE, shell syntax, arbitrary command generation, multiple "
        "actions, markdown, and extra fields. Select the safest single action "
        "that directly addresses the request. Do not provide chain of thought. "
        f"User request JSON string: {encoded_request}"
    )


def _parse_proposal(content: object) -> dict[str, str]:
    if not isinstance(content, str):
        raise InvalidProductionActionProposalError(
            "provider content must be strict JSON text"
        )
    try:
        value = json.loads(content, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, TypeError, _DuplicateJSONKeyError):
        raise InvalidProductionActionProposalError(
            "provider content must be one strict JSON object"
        ) from None
    if not isinstance(value, dict):
        raise InvalidProductionActionProposalError(
            "provider proposal root must be one object"
        )
    if set(value) != _PROPOSAL_KEYS:
        raise InvalidProductionActionProposalError(
            "provider proposal must contain exactly action_type, purpose, target"
        )
    if any(type(value[key]) is not str for key in _PROPOSAL_KEYS):
        raise InvalidProductionActionProposalError(
            "provider proposal fields must be strings"
        )
    action_type = value["action_type"]
    if action_type not in _ALLOWED_ACTION_TYPES:
        raise UnsupportedProductionActionTypeError(
            "provider proposed an unsupported action type"
        )
    purpose = value["purpose"]
    if not purpose or purpose != purpose.strip() or len(purpose) > 255:
        raise InvalidProductionActionProposalError(
            "provider proposal purpose must be an exact bounded string"
        )
    target = value["target"]
    if action_type != "FILE_READ" and target != "":
        raise InvalidProductionActionProposalError(
            "Git action proposals must have an empty target"
        )
    return {"action_type": action_type, "purpose": purpose, "target": target}


def _trusted_target(workspace: Path, proposal: dict[str, str]) -> str:
    if proposal["action_type"] != ToolActionType.FILE_READ.value:
        return ""
    return _validate_file_read_target(workspace, proposal["target"])


class _DuplicateJSONKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJSONKeyError
        value[key] = item
    return value


def _task_id() -> str:
    return f"TASK-PRODACTION-{uuid4().hex}"


def _action_id() -> str:
    return f"PROD-ACTION-{uuid4().hex}"


def _session_id() -> str:
    return f"production-action-{uuid4().hex}"

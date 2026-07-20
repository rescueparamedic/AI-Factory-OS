"""Application service for the single official AFDE Beta execution path."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from time import perf_counter
from typing import Any, Callable, Mapping
from uuid import uuid4

from afde.planner import ExecutionPlan, RuleBasedExecutionPlanner
from afde.providers import (
    AIProviderError, LiveAPIBlockedError, ProviderConfigurationError,
    ProviderRequestError, ProviderResponseError, create_provider,
)
from real_worker_runtime.artifact_store import ArtifactStore
from real_worker_runtime.models import ExecutionInput, WorkerExecutionResult
from real_worker_runtime.runtime_history import SESSION_ID_PATTERN
from real_worker_runtime.runtime_lifecycle import safe_message

from .pipeline import RealExecutionPipeline


EVIDENCE_SCHEMA_VERSION = "1.0"
EVIDENCE_FILENAME = "execution_evidence.json"
OFFICIAL_WORKER_ID = "development_worker"


class BetaExecutionInputError(ValueError):
    pass


class BetaEvidenceReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class BetaExecutionResult:
    schema_version: str
    execution_id: str
    session_id: str
    request_id: str
    status: str
    stage: str
    plan_id: str
    provider: str
    model: str
    execution_mode: str
    worker_id: str
    results: tuple[dict[str, Any], ...]
    evidence_path: str
    error: dict[str, Any] | None
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "status": self.status,
            "stage": self.stage,
            "plan_id": self.plan_id,
            "provider": self.provider,
            "model": self.model,
            "execution_mode": self.execution_mode,
            "worker_id": self.worker_id,
            "results": deepcopy(list(self.results)),
            "evidence_path": self.evidence_path,
            "error": deepcopy(self.error),
            "exit_code": self.exit_code,
        }


class BetaExecutionService:
    """Validate, invoke existing components, and persist bounded evidence."""

    def __init__(
        self, root: str | Path = ".", *,
        provider_factory: Callable[..., Any] = create_provider,
        pipeline_factory: Callable[..., RealExecutionPipeline] = RealExecutionPipeline,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.provider_factory = provider_factory
        self.pipeline_factory = pipeline_factory

    def evidence(self, session_id: str) -> dict[str, Any]:
        '''Read one persisted Beta execution Evidence document without mutation.'''
        path = _evidence_path(self.root, session_id)
        if not path.is_file():
            raise FileNotFoundError(session_id)
        try:
            value = json.loads(path.read_bytes().decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BetaEvidenceReadError(
                'execution Evidence is not valid UTF-8 JSON',
            ) from exc
        if not isinstance(value, Mapping):
            raise BetaEvidenceReadError(
                'execution Evidence root must be a JSON object',
            )
        persisted_session_id = value.get('session_id')
        if persisted_session_id is not None and persisted_session_id != session_id:
            raise BetaEvidenceReadError(
                'execution Evidence session ID does not match its path',
            )
        return _sanitize_evidence(value)

    def execute(
        self, request: str, provider: str = "mock", *,
        model: str | None = None, allow_live_api: bool = False,
        openai_client: Any | None = None,
    ) -> BetaExecutionResult:
        identity = _identity()
        started_at = _now()
        timer = perf_counter()
        stage = "input"
        plan: ExecutionPlan | None = None
        pipeline: RealExecutionPipeline | None = None
        results: tuple[WorkerExecutionResult, ...] = ()
        error: dict[str, Any] | None = None
        status = "failed"
        exit_code = 5
        provider_name = str(provider or "").strip().lower()
        selected_model: str | None = None
        execution_mode = "not_started"

        try:
            normalized_request = _request(request)
            provider_name = _provider(provider_name)
            selected_model = _selected_model(model)
            _validate_live_opt_in(provider_name, allow_live_api)
            stage = "planning"
            plan = RuleBasedExecutionPlanner().create_plan(normalized_request)
            stage = "provider"
            selected_provider = self.provider_factory(
                provider_name, model=selected_model,
                allow_live_api=allow_live_api, client=openai_client,
            )
            selected_model = (
                getattr(selected_provider, "model", None) or selected_model
            )
            execution_mode = (
                "live" if provider_name == "openai" else "deterministic"
            )
            pipeline = self.pipeline_factory(
                selected_provider, worker_id=OFFICIAL_WORKER_ID,
            )
            results = (pipeline.execute_task(plan, _execution_task(plan)),)
            stage = pipeline.last_stage
            if not results:
                raise RuntimeError("execution pipeline produced no worker result")
            failed = next(
                (item for item in results if item.execution_status != "completed"),
                None,
            )
            if failed is not None:
                stage = "worker"
                error = _normalized_worker_error(failed.error)
                exit_code = 5
            else:
                status = "completed"
                stage = "completed"
                exit_code = 0
            final = results[-1]
            selected_model = final.model
            execution_mode = final.execution_mode
        except Exception as exc:
            if pipeline is not None:
                stage = pipeline.last_stage
            error, exit_code = _normalized_error(exc, stage)

        completed_at = _now()
        evidence_path = _evidence_relative_path(identity["session_id"])
        evidence = _evidence(
            identity=identity,
            request=request,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=max(0, round((perf_counter() - timer) * 1000)),
            status=status,
            stage=stage,
            plan=plan,
            provider=provider_name,
            model=selected_model,
            execution_mode=execution_mode,
            pipeline=pipeline,
            results=results,
            error=error,
            evidence_path=evidence_path,
        )
        try:
            ArtifactStore(self.root, identity["session_id"]).json(
                EVIDENCE_FILENAME, evidence,
            )
        except Exception as exc:
            status = "failed"
            stage = "evidence"
            error = _evidence_error(exc)
            exit_code = 7
            evidence_path = ""

        return BetaExecutionResult(
            schema_version=EVIDENCE_SCHEMA_VERSION,
            execution_id=identity["execution_id"],
            session_id=identity["session_id"],
            request_id=identity["request_id"],
            status=status,
            stage=stage,
            plan_id=plan.plan_id if plan else "",
            provider=provider_name,
            model=selected_model or "",
            execution_mode=execution_mode,
            worker_id=OFFICIAL_WORKER_ID,
            results=tuple(_worker_summaries(results)),
            evidence_path=evidence_path,
            error=error,
            exit_code=exit_code,
        )


def _identity() -> dict[str, str]:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return {
        "execution_id": f"EXEC-{uuid4().hex}",
        "session_id": f"RWS-BETA-{stamp}-{uuid4().hex[:8]}",
        "request_id": f"REQ-{uuid4().hex}",
    }


def _execution_task(plan: ExecutionPlan):
    try:
        return next(task for task in plan.tasks if task.title == "Execute goal")
    except StopIteration as exc:
        raise RuntimeError("execution plan has no bounded execution task") from exc


def _request(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BetaExecutionInputError("request must not be empty")
    normalized = " ".join(value.split())
    if len(normalized) > 1000:
        raise BetaExecutionInputError("request must not exceed 1000 characters")
    return normalized


def _provider(value: str) -> str:
    if value not in {"mock", "openai"}:
        raise BetaExecutionInputError(f"unsupported Beta provider: {value or 'empty'}")
    return value


def _selected_model(value: str | None) -> str | None:
    if value is not None:
        selected = str(value).strip()
        if not selected:
            raise BetaExecutionInputError("model must not be empty")
        return selected
    selected = os.environ.get("AI_FACTORY_OPENAI_MODEL", "").strip()
    return selected or None


def _validate_live_opt_in(provider: str, allow_live_api: bool) -> None:
    if provider != "openai":
        return
    if not allow_live_api:
        raise LiveAPIBlockedError(
            "OpenAI Beta execution requires explicit --allow-live-api opt-in"
        )
    if os.environ.get("AI_FACTORY_RUN_LIVE_OPENAI_TESTS") != "1":
        raise LiveAPIBlockedError(
            "OpenAI Beta execution requires AI_FACTORY_RUN_LIVE_OPENAI_TESTS=1"
        )


def _normalized_worker_error(value: str) -> dict[str, Any]:
    return {
        "code": "BETA_WORKER_EXECUTION_FAILED",
        "category": "worker_execution",
        "stage": "worker",
        "message": _sanitize(value or "worker execution failed"),
        "retryable": False,
        "sanitized": True,
    }


def _normalized_error(exc: Exception, stage: str) -> tuple[dict[str, Any], int]:
    message = _sanitize(exc)
    retryable = False
    exit_code = 5
    code = "BETA_EXECUTION_FAILED"
    category = "execution"
    if isinstance(exc, BetaExecutionInputError):
        code, category, exit_code = "BETA_INVALID_INPUT", "invalid_input", 2
        stage = "input"
    elif isinstance(exc, (LiveAPIBlockedError, ProviderConfigurationError)):
        code, category, exit_code = (
            "BETA_PROVIDER_CONFIGURATION", "provider_configuration", 2,
        )
        stage = "provider"
    elif isinstance(exc, ProviderResponseError):
        code, category, stage = (
            "BETA_PROVIDER_RESPONSE", "provider_response", "provider",
        )
    elif isinstance(exc, ProviderRequestError):
        category = getattr(exc, "category", "provider_request")
        retryable = bool(getattr(exc, "retryable", True))
        if category == "provider_request":
            lowered = message.lower()
            if "timeout" in lowered:
                category = "provider_timeout"
            elif "authentication" in lowered or "permission" in lowered:
                category, retryable = "provider_authentication", False
        code = {
            "provider_timeout": "BETA_PROVIDER_TIMEOUT",
            "provider_authentication": "BETA_PROVIDER_AUTHENTICATION",
            "provider_rate_limit": "BETA_PROVIDER_RATE_LIMIT",
            "provider_server": "BETA_PROVIDER_SERVER",
        }.get(category, "BETA_PROVIDER_REQUEST")
        stage = "provider"
    elif isinstance(exc, AIProviderError):
        code, category, stage = "BETA_PROVIDER_FAILURE", "provider", "provider"
    elif stage == "bridge":
        code, category = "BETA_BRIDGE_CONVERSION", "bridge_conversion"
    elif stage == "planning":
        code, category = "BETA_PLANNING_FAILED", "planning"
    normalized = {
        "code": code,
        "category": category,
        "stage": stage,
        "message": message,
        "retryable": retryable,
        "sanitized": True,
    }
    if isinstance(exc, ProviderRequestError):
        status_code = getattr(exc, "status_code", None)
        request_id = getattr(exc, "request_id", None)
        if isinstance(status_code, int):
            normalized["http_status"] = status_code
        if request_id:
            normalized["provider_request_id"] = str(request_id)[:200]
    return normalized, exit_code


def _evidence_error(exc: Exception) -> dict[str, Any]:
    return {
        "code": "BETA_EVIDENCE_PERSISTENCE_FAILED",
        "category": "evidence_persistence",
        "stage": "evidence",
        "message": _sanitize(exc),
        "retryable": True,
        "sanitized": True,
    }


def _sanitize(value: Any) -> str:
    text = str(value or "execution failed")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    return safe_message(text)


def _evidence(
    *, identity: dict[str, str], request: Any, started_at: str,
    completed_at: str, duration_ms: int, status: str, stage: str,
    plan: ExecutionPlan | None, provider: str, model: str | None,
    execution_mode: str, pipeline: RealExecutionPipeline | None,
    results: tuple[WorkerExecutionResult, ...], error: dict[str, Any] | None,
    evidence_path: str,
) -> dict[str, Any]:
    runtime_evidence = {
        "status": "NOT_VERIFIED",
        "verified_changed_files": [],
        "verified_test_executions": [],
        "provider": provider,
        "model": model or "",
        "execution_mode": execution_mode,
        "plan_id": plan.plan_id if plan else "",
        "worker_id": OFFICIAL_WORKER_ID,
        "execution_status": status,
    }
    if pipeline and pipeline.last_evidence:
        runtime_evidence.update(pipeline.last_evidence)
        runtime_evidence["execution_status"] = status
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        **identity,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": duration_ms,
        "execution_status": status,
        "stage": stage,
        "request": _text_summary(request),
        "planner": _plan_summary(plan),
        "provider": {
            "name": provider,
            "model": model or "",
            "execution_mode": execution_mode,
        },
        "worker": {
            "worker_id": OFFICIAL_WORKER_ID,
            "mode": "single_worker",
            "execution_order": "sequential",
        },
        "provider_response_summary": _provider_summaries(pipeline),
        "worker_result_summary": _worker_summaries(results),
        "runtime_evidence": runtime_evidence,
        "error": deepcopy(error),
        "approval": {"required": False, "status": "not_applicable"},
        "artifacts": [{"type": "execution_evidence", "path": evidence_path}],
        "security": {
            "sanitized": True,
            "credentials_persisted": False,
            "authorization_headers_persisted": False,
            "environment_dumped": False,
        },
        "environment": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        },
    }


def _text_summary(value: Any) -> dict[str, Any]:
    sanitized = _sanitize(value)
    encoded = sanitized.encode("utf-8")
    return {
        "summary": sanitized[:240],
        "length": len(sanitized),
        "sha256": sha256(encoded).hexdigest(),
    }


def _plan_summary(plan: ExecutionPlan | None) -> dict[str, Any]:
    if plan is None:
        return {"available": False, "plan_id": "", "task_count": 0, "tasks": []}
    return {
        "available": True,
        "planner": "RuleBasedExecutionPlanner",
        "plan_id": plan.plan_id,
        "status": plan.status,
        "task_count": len(plan.tasks),
        "goal": _text_summary(plan.goal),
        "tasks": [
            {
                "task_id": task.task_id,
                "title": _sanitize(task.title)[:120],
                "status": task.status,
                "depends_on": list(task.depends_on),
            }
            for task in plan.tasks
        ],
    }


def _provider_summaries(
    pipeline: RealExecutionPipeline | None,
) -> list[dict[str, Any]]:
    inputs: tuple[ExecutionInput, ...] = (
        pipeline.execution_inputs if pipeline is not None else ()
    )
    return [
        {
            "task_id": item.task_id,
            "provider": item.provider,
            "model": item.model,
            "execution_mode": item.execution_mode,
            "content_length": len(item.instruction),
            "content_sha256": sha256(item.instruction.encode("utf-8")).hexdigest(),
        }
        for item in inputs
    ]


def _worker_summaries(
    results: tuple[WorkerExecutionResult, ...],
) -> list[dict[str, Any]]:
    return [
        {
            "task_id": item.task_id,
            "worker_id": item.worker_id,
            "execution_status": item.execution_status,
            "started_at": item.started_at,
            "completed_at": item.completed_at,
            "output_keys": sorted(str(key) for key in item.output),
            "error": _sanitize(item.error) if item.error else "",
        }
        for item in results
    ]


_SENSITIVE_FIELD = re.compile(
    r'(?:authorization|api[_-]?key|secret|password|token|credential|private[_-]?key)',
    re.IGNORECASE,
)
_SENSITIVE_TEXT = (
    re.compile(r'(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+'),
    re.compile(r'(?i)((?:api[_-]?key|secret|password|token|credential|private[_-]?key)\s*[:=]\s*)[^\s,;]+'),
    re.compile(r'(?i)(\bbearer\s+)[^\s,;]+'),
    re.compile(r'\bsk-[A-Za-z0-9_-]{8,}\b'),
)
_CONTROL_TEXT = re.compile(r'[\x00-\x1f\x7f]')


def _evidence_path(root: Path, session_id: str) -> Path:
    if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
        raise BetaExecutionInputError('invalid Beta execution session ID')
    workspace = root.resolve()
    sessions = workspace / 'data' / 'runtime_sessions'
    session = sessions / session_id
    evidence = session / EVIDENCE_FILENAME
    for candidate in (sessions, session, evidence):
        if candidate.exists() and _is_redirected(candidate):
            raise BetaExecutionInputError(
                'Beta execution Evidence path must not use a link or junction',
            )
    resolved_sessions = sessions.resolve()
    resolved_session = session.resolve()
    resolved_evidence = evidence.resolve()
    if (
        not resolved_sessions.is_relative_to(workspace)
        or not resolved_session.is_relative_to(resolved_sessions)
        or not resolved_evidence.is_relative_to(resolved_session)
        or resolved_evidence.parent != resolved_session
    ):
        raise BetaExecutionInputError(
            'Beta execution Evidence must remain inside the workspace',
        )
    return resolved_evidence


def _is_redirected(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, 'is_junction', None)
    return bool(is_junction and is_junction())


def _sanitize_evidence(value: Any, field: str = '') -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _sanitize_evidence(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_evidence(item, field) for item in value]
    if isinstance(value, str):
        if _SENSITIVE_FIELD.search(field):
            return '[REDACTED]'
        return _sanitize_evidence_text(value)
    return deepcopy(value)


def _sanitize_evidence_text(value: str) -> str:
    sanitized = _CONTROL_TEXT.sub(' ', value)
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if api_key:
        sanitized = sanitized.replace(api_key, '[REDACTED]')
    for pattern in _SENSITIVE_TEXT:
        sanitized = pattern.sub(
            lambda match: (
                f'{match.group(1)}[REDACTED]' if match.lastindex else '[REDACTED]'
            ),
            sanitized,
        )
    return sanitized


def _evidence_relative_path(session_id: str) -> str:
    return f"data/runtime_sessions/{session_id}/{EVIDENCE_FILENAME}"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .controlled_execution import (
    ActionType, ExecutionRequest, execution_action_fingerprint,
)
from .errors import RuntimeSessionError


PENDING = "PENDING"
APPROVED = "APPROVED"
REJECTED = "REJECTED"
CONSUMED = "CONSUMED"


class RuntimeApprovalStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.directory = self.root / "data" / "pending_approvals"

    def create(
        self, request: ExecutionRequest, session_id: str, sprint_id: str,
        guardian: dict[str, Any],
    ) -> dict[str, Any]:
        payload = normalized_action_payload(request)
        now = _now()
        record = {
            "approval_request_id": f"APR-{uuid4().hex}",
            "execution_request_id": request.request_id,
            "session_id": session_id,
            "sprint_id": sprint_id,
            "source_worker": request.source_worker,
            "action_type": request.action_type.value,
            "normalized_action_payload": payload,
            "target": request.relative_path if request.action_type is ActionType.FILE_WRITE else list(request.argv),
            "action_fingerprint": action_fingerprint(request),
            "context_fingerprint": guardian.get("context_fingerprint", ""),
            "normalized_context": guardian.get("normalized_context", {}),
            "guardian_policy_classification": guardian.get("policy_classification"),
            "guardian_rule_id": guardian.get("rule_id") or guardian.get("guardian_rule_id"),
            "guardian_reason": guardian.get("reason") or guardian.get("guardian_reason"),
            "created_at": now,
            "status": PENDING,
            "approved_at": None,
            "approved_by": None,
            "revalidation_result": None,
            "consumed_at": None,
            "rejected_at": None,
        }
        self._save(record)
        return record

    def load(self, approval_id: str) -> dict[str, Any]:
        if not approval_id.startswith("APR-") or not approval_id[4:].isalnum():
            raise RuntimeSessionError("unknown approval_request_id")
        path = self.directory / f"{approval_id}.json"
        if not path.is_file():
            raise RuntimeSessionError("unknown approval_request_id")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeSessionError("pending approval record is missing or corrupt") from exc
        if record.get("approval_request_id") != approval_id:
            raise RuntimeSessionError("approval record identity mismatch")
        return record

    def approve(self, approval_id: str, approved_by: str = "Product Owner") -> dict[str, Any]:
        record = self.load(approval_id)
        if record.get("status") != PENDING:
            raise RuntimeSessionError(f"approval is not pending: {record.get('status')}")
        record["status"] = APPROVED
        record["approved_at"] = _now()
        record["approved_by"] = str(approved_by or "Product Owner")[:100]
        record["revalidation_result"] = "pending"
        self._save(record)
        return record

    def reject(self, approval_id: str) -> dict[str, Any]:
        record = self.load(approval_id)
        if record.get("status") != PENDING:
            raise RuntimeSessionError(f"approval is not pending: {record.get('status')}")
        record["status"] = REJECTED
        record["rejected_at"] = _now()
        self._save(record)
        return record

    def consume(self, record: dict[str, Any]) -> dict[str, Any]:
        current = self.load(record["approval_request_id"])
        if current.get("status") != APPROVED:
            raise RuntimeSessionError("approval cannot be consumed")
        if current != record:
            raise RuntimeSessionError("approval record changed before consumption")
        current["status"] = CONSUMED
        current["consumed_at"] = _now()
        self._save(current)
        return current

    def mark_revalidated(self, record: dict[str, Any]) -> dict[str, Any]:
        current = self.load(record["approval_request_id"])
        if current != record or current.get("status") != APPROVED:
            raise RuntimeSessionError("approval changed before revalidation")
        current["revalidation_result"] = "matched"
        current["revalidated_at"] = _now()
        self._save(current)
        return current

    def record_invalidation(self, approval_id: str, reason: str) -> dict[str, Any]:
        current = self.load(approval_id)
        if current.get("status") != PENDING:
            raise RuntimeSessionError("only a pending approval can be invalidated")
        current["revalidation_result"] = "mismatch"
        current["invalidation_reason"] = str(reason)[:500]
        current["invalidated_at"] = _now()
        self._save(current)
        return current

    def _save(self, record: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{record['approval_request_id']}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)


def normalized_action_payload(request: ExecutionRequest) -> dict[str, Any]:
    if request.action_type is ActionType.FILE_WRITE:
        return {
            "relative_path": request.relative_path,
            "content": request.content,
            "expected_preimage_sha256": request.expected_preimage_sha256,
            "purpose": request.purpose,
        }
    return {"argv": list(request.argv), "purpose": request.purpose}


def action_fingerprint(request: ExecutionRequest) -> str:
    return execution_action_fingerprint(request)


def fingerprint_matches(request: ExecutionRequest, fingerprint: Any) -> bool:
    return fingerprint in {action_fingerprint(request), _legacy_action_fingerprint(request)}


def _legacy_action_fingerprint(request: ExecutionRequest) -> str:
    canonical = {
        "execution_request_id": request.request_id,
        "action_type": request.action_type.value,
        "source_worker": request.source_worker,
        "payload": normalized_action_payload(request),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def request_from_record(record: dict[str, Any]) -> ExecutionRequest:
    payload = record.get("normalized_action_payload")
    if not isinstance(payload, dict):
        raise RuntimeSessionError("approval action payload is invalid")
    try:
        action = ActionType(record["action_type"])
        if action is ActionType.FILE_WRITE:
            request = ExecutionRequest(
                request_id=record["execution_request_id"], action_type=action,
                source_worker=record["source_worker"], purpose=payload["purpose"],
                relative_path=payload["relative_path"], content=payload["content"],
                expected_preimage_sha256=payload.get("expected_preimage_sha256"),
            )
        else:
            request = ExecutionRequest(
                request_id=record["execution_request_id"], action_type=action,
                source_worker=record["source_worker"], purpose=payload["purpose"],
                argv=tuple(payload["argv"]),
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeSessionError("approval action payload is invalid") from exc
    if not fingerprint_matches(request, record.get("action_fingerprint")):
        raise RuntimeSessionError("approval action fingerprint mismatch")
    expected_target = request.relative_path if action is ActionType.FILE_WRITE else list(request.argv)
    if expected_target != record.get("target"):
        raise RuntimeSessionError("approval target mismatch")
    return request


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

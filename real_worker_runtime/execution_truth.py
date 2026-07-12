from __future__ import annotations

from copy import deepcopy
from typing import Any


UNVERIFIED_FILE_CHANGE_CLAIM = "UNVERIFIED_FILE_CHANGE_CLAIM"
UNVERIFIED_TEST_EXECUTION_CLAIM = "UNVERIFIED_TEST_EXECUTION_CLAIM"


def apply_execution_truth_contract(
    worker_id: str, output: dict[str, Any], runtime_evidence: dict[str, Any] | None = None
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Separate provider claims from evidence observed by the Runtime itself."""
    normalized = deepcopy(output)
    evidence = runtime_evidence or {}
    findings: list[dict[str, Any]] = []

    if worker_id == "development_worker":
        proposed = _string_list(normalized.pop("proposed_files", None))
        proposed += _string_list(normalized.pop("changed_files", None))
        proposed = _unique(proposed)
        normalized["proposed_files"] = proposed
        normalized["proposed_test_commands"] = _unique(
            _string_list(normalized.pop("proposed_test_commands", None))
            + _string_list(normalized.pop("commands_requested", None))
        )
        normalized["claimed_artifacts"] = _string_list(
            normalized.pop("claimed_artifacts", normalized.pop("artifacts", None))
        )
        verified = _string_list(evidence.get("verified_changed_files"))
        normalized["verified_changed_files"] = verified
        unsupported = [item for item in proposed if item not in verified]
        if unsupported:
            findings.append(_finding(UNVERIFIED_FILE_CHANGE_CLAIM, unsupported))

    if worker_id == "qa_worker":
        claimed_commands = _unique(
            _string_list(normalized.pop("claimed_test_commands", None))
            + _string_list(normalized.pop("tests_run", None))
        )
        passed = _nonnegative_int(normalized.pop("claimed_passed", normalized.pop("passed", 0)))
        failed = _nonnegative_int(normalized.pop("claimed_failed", normalized.pop("failed", 0)))
        normalized["claimed_test_commands"] = claimed_commands
        normalized["claimed_test_results"] = {
            "passed": passed,
            "failed": failed,
            "recommendation": normalized.get("recommendation"),
        }
        verified_executions = evidence.get("verified_test_executions")
        normalized["verified_test_executions"] = (
            deepcopy(verified_executions) if isinstance(verified_executions, list) else []
        )
        if (claimed_commands or passed or failed) and not normalized["verified_test_executions"]:
            findings.append(
                _finding(UNVERIFIED_TEST_EXECUTION_CLAIM, claimed_commands or [f"passed={passed}", f"failed={failed}"])
            )

    if findings:
        normalized["truth_contract_findings"] = findings
    return normalized, findings


def claimed_qa_failures(output: dict[str, Any]) -> int:
    results = output.get("claimed_test_results", {})
    return _nonnegative_int(results.get("failed", 0)) if isinstance(results, dict) else 0


def _finding(classification: str, claims: list[str]) -> dict[str, Any]:
    return {"classification": classification, "claimed_items": claims[:20]}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item[:255] for item in value if isinstance(item, str) and item]


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0

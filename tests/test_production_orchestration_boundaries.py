import ast
from pathlib import Path

import afde
import afde.production_orchestration as orchestration_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "afde" / "production_orchestration"


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_orchestration_stops_at_runtime_execution_boundary():
    imports = {item for path in PACKAGE.glob("*.py") for item in _imports(path)}
    forbidden = {
        "afde.production_adapter_worker_execution",
        "afde.production_adapter_runtime_observation",
        "afde.production_adapter_runtime_event_collection",
        "afde.production_adapter_runtime_event_stream",
        "afde.execution",
        "afde.product",
        "afde.operator",
        "os_core.worker_manager",
        "runtime",
        "worker_runtime",
        "workers",
    }
    assert not {
        item for item in imports
        if any(
            item == blocked or item.startswith(blocked + ".")
            for blocked in forbidden
        )
    }


def test_orchestration_does_not_read_secrets_or_add_beta_fallback():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
    )
    for token in (
        "getenv(", "environ", "keyring", "load_credentials", "afde.cli",
        "RealWorkerRuntime", "ProductionAdapterWorkerExecutionService",
    ):
        assert token not in source


def test_public_contract_is_additive_and_package_scoped():
    assert not hasattr(afde, "ProductionPlannerRuntimeOrchestrator")
    assert orchestration_package.__all__ == [
        "InvalidProductionOrchestrationRequestError",
        "InvalidProductionOrchestrationResultError",
        "ProductionOrchestrationError",
        "ProductionOrchestrationRequest",
        "ProductionOrchestrationResult",
        "ProductionOrchestrationStatus",
        "ProductionPlannerRuntimeOrchestrator",
        "RuntimeExecutionAuthorityProvider",
    ]

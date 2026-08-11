import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "afde" / "production_planner_worker_dispatch"


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_dispatch_depends_only_on_approved_production_and_worker_contracts():
    imports = {item for path in PACKAGE.glob("*.py") for item in _imports(path)}
    assert {
        "afde.production_orchestration",
        "afde.production_adapter_worker_execution",
        "real_worker_runtime.models",
    }.issubset(imports)
    forbidden = {
        "afde.production_adapter_runtime_observation",
        "afde.production_adapter_runtime_event_collection",
        "afde.production_adapter_runtime_event_stream",
        "real_worker_runtime.provider_bridge",
        "real_worker_runtime.runtime",
        "real_worker_runtime.runtime_history",
        "afde.cli",
    }
    assert not {
        item for item in imports
        if any(item == blocked or item.startswith(blocked + ".") for blocked in forbidden)
    }


def test_dispatch_has_no_runtime_execution_authority_or_second_execute_call():
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
    )
    assert "ProductionAdapterRuntimeExecutionAuthority" not in source
    assert ".execute(" not in source
    assert "RealWorkerRuntime" not in source
    assert "EventStream" not in source

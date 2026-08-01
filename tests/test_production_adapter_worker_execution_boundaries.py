import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_EXECUTION = ROOT / "afde" / "production_adapter_worker_execution"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.providers",
    "real_worker_runtime.automation_bridge",
    "real_worker_runtime.provider_bridge",
    "real_worker_runtime.runtime",
    "real_worker_runtime.runtime_lifecycle",
    "real_worker_runtime.runtime_orchestrator",
    "real_worker_runtime.worker_registry",
    "worker_runtime",
    "workers",
}


def test_worker_execution_uses_only_runtime_and_worker_contracts():
    imports = set()
    for path in WORKER_EXECUTION.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert {
        "afde.production_adapter_runtime_execution",
        "real_worker_runtime.models",
    }.issubset(imports)
    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_worker_execution_has_no_lifecycle_provider_or_dispatch_calls():
    called_attributes = set()
    for path in WORKER_EXECUTION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called_attributes.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        )

    assert "execute" in called_attributes
    assert not called_attributes.intersection(
        {
            "select",
            "generate",
            "dispatch",
            "start",
            "stop",
            "transition",
            "record",
            "list",
        }
    )


def test_protected_runtime_and_worker_layers_do_not_import_new_package():
    protected = (
        ROOT / "runtime",
        ROOT / "real_worker_runtime",
        ROOT / "worker_runtime",
        ROOT / "workers",
        ROOT / "afde" / "execution",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
            assert not {
                item
                for item in imports
                if item.startswith(
                    "afde.production_adapter_worker_execution"
                )
            }


def test_worker_execution_dependency_is_one_way():
    runtime_execution = (
        ROOT / "afde" / "production_adapter_runtime_execution"
    )
    for path in runtime_execution.glob("*.py"):
        imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
        assert not {
            item
            for item in imports
            if item.startswith("afde.production_adapter_worker_execution")
        }


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

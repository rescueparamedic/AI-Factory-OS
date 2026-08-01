import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "afde" / "production_adapter_runtime_execution"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.product",
    "afde.providers",
    "cli",
    "httpx",
    "keyring",
    "requests",
    "socket",
    "subprocess",
    "worker_runtime",
    "workers",
}


def test_runtime_execution_package_reuses_only_foundation_dependencies():
    imports = set()
    for path in EXECUTION.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert {
        "afde.production_adapter_creation",
        "afde.production_adapter_invocation",
        "afde.production_adapter_runtime_startup_integration",
        "afde.tool_adapter_contract",
    }.issubset(imports)
    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_runtime_execution_boundary_has_no_lifecycle_or_worker_calls():
    tree = ast.parse((EXECUTION / "service.py").read_text(encoding="utf-8"))
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"create", "invoke"}.issubset(called_attributes)
    assert not called_attributes.intersection(
        {
            "start",
            "stop",
            "pause",
            "resume",
            "transition",
            "dispatch",
            "connect",
            "commit",
            "rollback",
        }
    )


def test_existing_runtime_and_application_layers_do_not_import_execution_package():
    protected = (
        ROOT / "afde" / "desktop",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "runtime",
        ROOT / "real_worker_runtime",
        ROOT / "worker_runtime",
        ROOT / "workers",
        ROOT / "cli",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
            assert not {
                item
                for item in imports
                if item.startswith("afde.production_adapter_runtime_execution")
            }


def test_authority_consumption_ledger_is_private_and_runtime_isolated():
    service_source = (EXECUTION / "service.py").read_text(encoding="utf-8")
    package_source = (EXECUTION / "__init__.py").read_text(encoding="utf-8")

    assert "from threading import Lock" in service_source
    assert "_AUTHORITY_CONSUMPTION_LEDGER" in service_source
    assert "_AUTHORITY_CONSUMPTION_LEDGER" not in package_source
    for path in EXECUTION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = (
                    [target.id for target in node.targets]
                    if isinstance(node, ast.Assign)
                    else [node.target.id]
                )
                if names == ["__all__"] or names[0].endswith("_PATTERN"):
                    continue
                assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

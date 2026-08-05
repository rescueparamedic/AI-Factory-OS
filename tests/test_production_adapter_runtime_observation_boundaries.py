import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVATION = ROOT / "afde" / "production_adapter_runtime_observation"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.runtime_history",
    "afde.runtime_monitoring",
    "real_worker_runtime.runtime",
    "runtime",
    "sqlite3",
    "threading",
    "time",
    "worker_runtime",
    "workers",
}


def test_observation_depends_only_on_existing_worker_execution_contract():
    imports = set()
    for path in OBSERVATION.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert "afde.production_adapter_worker_execution" in imports
    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_observation_has_no_collection_monitoring_or_execution_calls():
    called_attributes = set()
    for path in OBSERVATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called_attributes.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        )

    assert not called_attributes.intersection(
        {
            "append",
            "collect",
            "execute",
            "invoke",
            "monitor",
            "poll",
            "record",
            "schedule",
            "start",
            "store",
            "write",
        }
    )


def test_runtime_and_worker_execution_do_not_import_observation_package():
    protected = (
        ROOT / "afde" / "production_adapter_runtime_execution",
        ROOT / "afde" / "production_adapter_worker_execution",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
            assert not {
                item
                for item in imports
                if item.startswith("afde.production_adapter_runtime_observation")
            }


def test_observation_package_has_no_mutable_module_state():
    for path in OBSERVATION.glob("*.py"):
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

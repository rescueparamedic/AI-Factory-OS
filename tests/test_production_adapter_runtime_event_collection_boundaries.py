import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = ROOT / "afde" / "production_adapter_runtime_event_collection"
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "afde.production_adapter_runtime_observation",
    "afde.production_adapter_runtime_execution",
    "afde.production_adapter_worker_execution",
    "io",
    "pathlib",
    "queue",
    "real_worker_runtime",
    "sqlite3",
    "threading",
    "time",
}


def test_event_collection_has_no_stream_storage_or_runtime_dependencies():
    imports = set()
    for path in COLLECTION.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_service_has_one_synchronous_non_generator_public_operation():
    tree = ast.parse((COLLECTION / "service.py").read_text(encoding="utf-8"))
    service = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ProductionAdapterRuntimeEventCollectionService"
    )
    public_methods = [
        node
        for node in service.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]

    assert [method.name for method in public_methods] == ["collect"]
    assert type(public_methods[0]) is ast.FunctionDef
    assert not any(
        isinstance(node, (ast.Yield, ast.YieldFrom, ast.AsyncFor, ast.Await))
        for node in ast.walk(public_methods[0])
    )


def test_boundary_has_no_background_persistence_or_delivery_calls():
    forbidden_calls = {
        "append",
        "connect",
        "execute",
        "invoke",
        "open",
        "poll",
        "publish",
        "put",
        "record",
        "replay",
        "schedule",
        "start",
        "subscribe",
        "write",
    }
    called_attributes = set()
    for path in COLLECTION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called_attributes.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        )

    assert not called_attributes.intersection(forbidden_calls)


def test_existing_observation_runtime_and_worker_packages_do_not_depend_on_collection():
    protected = (
        ROOT / "afde" / "production_adapter_runtime_observation",
        ROOT / "afde" / "production_adapter_runtime_execution",
        ROOT / "afde" / "production_adapter_worker_execution",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            imports = _imports(ast.parse(path.read_text(encoding="utf-8")))
            assert not {
                item
                for item in imports
                if item.startswith(
                    "afde.production_adapter_runtime_event_collection"
                )
            }


def test_event_collection_package_has_no_mutable_module_state():
    for path in COLLECTION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = (
                    [target.id for target in node.targets]
                    if isinstance(node, ast.Assign)
                    else [node.target.id]
                )
                if names == ["__all__"]:
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

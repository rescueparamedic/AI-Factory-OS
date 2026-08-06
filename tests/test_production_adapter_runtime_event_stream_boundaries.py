import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STREAM = ROOT / "afde" / "production_adapter_runtime_event_stream"
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "afde.production_adapter_runtime_observation",
    "afde.production_adapter_runtime_execution",
    "afde.production_adapter_worker_execution",
    "io",
    "multiprocessing",
    "pathlib",
    "queue",
    "real_worker_runtime",
    "sqlite3",
    "threading",
    "time",
}


def test_event_stream_has_no_storage_monitoring_or_runtime_dependencies():
    imports = set()
    for path in STREAM.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_service_has_synchronous_non_generator_lifecycle_operations():
    tree = ast.parse((STREAM / "service.py").read_text(encoding="utf-8"))
    service = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "ProductionAdapterRuntimeEventStreamService"
    )
    public_methods = [
        node
        for node in service.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    ]

    assert [method.name for method in public_methods] == [
        "state",
        "snapshot",
        "open",
        "append",
        "close",
        "stream",
    ]
    for method in public_methods:
        assert type(method) is ast.FunctionDef
        assert not any(
            isinstance(node, (ast.Yield, ast.YieldFrom, ast.AsyncFor, ast.Await))
            for node in ast.walk(method)
        )


def test_boundary_has_no_background_persistence_delivery_or_query_calls():
    forbidden_calls = {
        "aggregate",
        "connect",
        "execute",
        "invoke",
        "monitor",
        "poll",
        "publish",
        "put",
        "query",
        "record",
        "replay",
        "schedule",
        "start",
        "subscribe",
        "write",
    }
    called_attributes = set()
    for path in STREAM.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called_attributes.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        )

    assert not called_attributes.intersection(forbidden_calls)


def test_stream_never_calls_or_wraps_event_collection_service():
    for path in STREAM.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(node, ast.Name)
            and node.id == "ProductionAdapterRuntimeEventCollectionService"
            for node in ast.walk(tree)
        )
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "collect"
            for node in ast.walk(tree)
        )


def test_existing_collection_observation_and_execution_do_not_depend_on_stream():
    protected = (
        ROOT / "afde" / "production_adapter_runtime_event_collection",
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
                if item.startswith("afde.production_adapter_runtime_event_stream")
            }


def test_event_stream_package_has_no_mutable_module_state():
    for path in STREAM.glob("*.py"):
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

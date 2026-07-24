import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_PATH = ROOT / "afde" / "execution_path"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.knowledge.loader",
    "afde.knowledge.provider",
    "afde.operator",
    "afde.product",
    "afde.providers",
    "json",
    "os",
    "pathlib",
    "real_worker_runtime",
    "requests",
    "runtime",
    "socket",
    "subprocess",
    "urllib",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "cancel",
    "dispatch",
    "execute",
    "invoke",
    "open",
    "read_bytes",
    "read_text",
    "resume",
    "run",
    "start",
    "write_bytes",
    "write_text",
}


def test_execution_path_has_no_runtime_worker_product_provider_or_io_boundary():
    for path in EXECUTION_PATH.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _imports(tree)
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }
        attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }

        assert not {
            item
            for item in imports
            if any(
                item == forbidden or item.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_IMPORT_ROOTS
            )
        }
        assert not calls.intersection(FORBIDDEN_CALLS)
        assert not attributes.intersection(FORBIDDEN_CALLS)


def test_upstream_and_lower_layers_do_not_reverse_import_execution_path():
    directories = (
        ROOT / "afde" / "knowledge",
        ROOT / "afde" / "planner",
        ROOT / "afde" / "planner_resolution",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "afde" / "resolver",
        ROOT / "afde" / "tool_catalog",
        ROOT / "afde" / "tool_selection",
        ROOT / "runtime",
        ROOT / "workers",
    )
    for directory in directories:
        for path in directory.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
            assert not {
                item for item in _imports(tree)
                if item.startswith("afde.execution_path")
            }


def test_execution_path_has_no_mutable_global_or_hidden_service_construction():
    for path in EXECUTION_PATH.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = (
                    [target.id for target in node.targets]
                    if isinstance(node, ast.Assign)
                    else [node.target.id]
                )
                if names == ["__all__"]:
                    continue
                assert not isinstance(
                    node.value, (ast.Dict, ast.List, ast.Set),
                )
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        }
        assert "ToolAdapterCatalog" not in constructed
        assert "ToolAdapterSelectionService" not in constructed


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

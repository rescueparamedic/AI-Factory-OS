import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "afde" / "tool_catalog"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.knowledge.loader",
    "afde.knowledge.provider",
    "afde.operator",
    "afde.product",
    "afde.providers",
    "json",
    "pathlib",
    "real_worker_runtime",
    "requests",
    "runtime",
    "socket",
    "urllib",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "execute",
    "invoke",
    "open",
    "read_bytes",
    "read_text",
    "run",
    "write_bytes",
    "write_text",
}


def test_catalog_has_no_registry_runtime_worker_product_provider_or_io_boundary():
    for path in CATALOG.glob("*.py"):
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


def test_lower_layers_and_selection_do_not_reverse_import_catalog():
    directories = (
        ROOT / "afde" / "knowledge",
        ROOT / "afde" / "planner",
        ROOT / "afde" / "planner_resolution",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "afde" / "resolver",
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
                if item.startswith("afde.tool_catalog")
            }


def test_catalog_has_no_module_level_mutable_singleton():
    for path in CATALOG.glob("*.py"):
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
                value = node.value
                assert not isinstance(
                    value, (ast.Dict, ast.List, ast.Set),
                )


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

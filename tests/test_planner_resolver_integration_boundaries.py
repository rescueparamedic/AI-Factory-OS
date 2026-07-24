import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "afde" / "planner_resolution"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.operator",
    "afde.product",
    "afde.providers",
    "json",
    "pathlib",
    "real_worker_runtime",
    "requests",
    "socket",
    "urllib",
}
FORBIDDEN_CALLS = {
    "open",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
}


def test_integration_has_no_runtime_tool_product_network_or_io_boundary():
    for path in INTEGRATION.glob("*.py"):
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


def test_planner_and_resolver_do_not_reverse_import_integration():
    for directory in (ROOT / "afde" / "planner", ROOT / "afde" / "resolver"):
        for path in directory.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
            assert not {
                item for item in _imports(tree)
                if item.startswith("afde.planner_resolution")
            }


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                result.add(node.module)
    return result

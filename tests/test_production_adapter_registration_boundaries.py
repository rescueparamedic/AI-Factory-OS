import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRATION = ROOT / "afde" / "production_adapter_registration"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.execution",
    "afde.knowledge",
    "afde.non_executable_composition",
    "afde.operator",
    "afde.product",
    "afde.production_composition",
    "afde.providers",
    "afde.runtime_integration",
    "afde.tool_adapter_contract",
    "afde.tool_selection",
    "importlib",
    "json",
    "os",
    "pathlib",
    "real_worker_runtime",
    "requests",
    "runtime",
    "socket",
    "subprocess",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "__import__",
    "dispatch",
    "execute",
    "find_spec",
    "getenv",
    "import_module",
    "invoke",
    "load",
    "open",
    "read_bytes",
    "read_text",
    "run",
    "start",
    "write_bytes",
    "write_text",
}


def test_registration_has_only_descriptor_and_registry_dependencies():
    for path in REGISTRATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _imports(tree)
        assert not {
            item for item in imports
            if any(
                item == forbidden or item.startswith(f"{forbidden}.")
                for forbidden in FORBIDDEN_IMPORT_ROOTS
            )
        }
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
        assert not calls.intersection(FORBIDDEN_CALLS)
        assert not attributes.intersection(FORBIDDEN_CALLS)


def test_runtime_worker_provider_layers_do_not_reverse_import_registration():
    directories = (
        ROOT / "afde" / "operator",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "real_worker_runtime",
        ROOT / "runtime",
        ROOT / "worker_runtime",
        ROOT / "workers",
    )
    for directory in directories:
        for path in directory.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
            assert not {
                item for item in _imports(tree)
                if item.startswith("afde.production_adapter_registration")
            }


def test_registration_has_no_mutable_global_or_behavior_facade():
    forbidden_methods = {
        "bind",
        "dispatch",
        "execute",
        "invoke",
        "run",
        "start",
    }
    for path in REGISTRATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert not methods.intersection(forbidden_methods)
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

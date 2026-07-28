import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "afde" / "production_adapter_discovery"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.operator",
    "afde.product",
    "afde.providers",
    "afde.runtime_integration",
    "json",
    "os",
    "pathlib",
    "pkgutil",
    "pluggy",
    "requests",
    "runtime",
    "socket",
    "stevedore",
    "subprocess",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "bind",
    "dispatch",
    "execute",
    "find_spec",
    "getenv",
    "glob",
    "import_module",
    "invoke",
    "iter_modules",
    "open",
    "probe",
    "read_bytes",
    "read_text",
    "rglob",
    "run",
    "start",
    "walk",
    "write_bytes",
    "write_text",
}


def test_discovery_uses_only_allowed_metadata_and_registry_dependencies():
    imports = set()
    attributes = set()
    calls = set()
    for path in DISCOVERY.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports.update(_imports(tree))
        calls.update(
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
        )
        attributes.update(
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        )

    assert "importlib.metadata" in imports
    assert not {
        item for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }
    assert not calls.intersection(FORBIDDEN_CALLS)
    assert not attributes.intersection(FORBIDDEN_CALLS)


def test_importlib_metadata_is_called_in_only_one_module():
    importing = []
    for path in ROOT.rglob("*.py"):
        if any(part.startswith(".") for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if "importlib.metadata" in _imports(tree):
            importing.append(path.relative_to(ROOT).as_posix())

    assert importing == [
        "afde/production_adapter_discovery/discovery.py",
    ]


def test_runtime_worker_cli_and_desktop_do_not_import_discovery():
    directories = (
        ROOT / "afde" / "desktop",
        ROOT / "afde" / "operator",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "cli",
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
                if item.startswith("afde.production_adapter_discovery")
            }


def test_discovery_exposes_no_adapter_or_lifecycle_behavior():
    forbidden_methods = {
        "bind",
        "check_credentials",
        "dispatch",
        "execute",
        "health_check",
        "invoke",
        "probe",
        "run",
        "start",
    }
    for path in DISCOVERY.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert not methods.intersection(forbidden_methods)


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "importlib":
                result.update(
                    f"importlib.{alias.name}" for alias in node.names
                )
            else:
                result.add(node.module)
    return result

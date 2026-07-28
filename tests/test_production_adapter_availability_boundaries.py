import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AVAILABILITY = ROOT / "afde" / "production_adapter_availability"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.execution_path",
    "afde.operator",
    "afde.product",
    "afde.production_adapter_discovery",
    "afde.providers",
    "afde.runtime_integration",
    "cli",
    "importlib",
    "json",
    "os",
    "pathlib",
    "pkgutil",
    "requests",
    "runtime",
    "socket",
    "subprocess",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "bind",
    "check_credentials",
    "dispatch",
    "execute",
    "find_spec",
    "getenv",
    "health_check",
    "import_module",
    "invoke",
    "load",
    "lookup_credentials",
    "open",
    "probe",
    "run",
    "start",
}


def test_package_depends_only_on_existing_descriptor_metadata():
    imports = set()
    calls = set()
    attributes = set()
    accessed_attributes = set()
    for path in AVAILABILITY.glob("*.py"):
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
        accessed_attributes.update(
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        )

    assert "afde.tool_catalog" in imports
    assert not {
        item for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }
    assert not calls.intersection(FORBIDDEN_CALLS)
    assert not attributes.intersection(FORBIDDEN_CALLS)
    assert "credentials_required" not in accessed_attributes


def test_runtime_worker_provider_product_cli_and_desktop_do_not_import_package():
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
                if item.startswith(
                    "afde.production_adapter_availability"
                )
            }


def test_package_exposes_no_forbidden_behavior_or_mutable_global():
    forbidden_methods = {
        "bind",
        "check_credentials",
        "dispatch",
        "execute",
        "health_check",
        "invoke",
        "lookup_credentials",
        "probe",
        "run",
        "start",
    }
    for path in AVAILABILITY.glob("*.py"):
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


def test_registry_catalog_execution_and_runtime_sources_are_unchanged():
    protected = (
        ROOT / "afde" / "operational_adapter_registry",
        ROOT / "afde" / "tool_catalog",
        ROOT / "afde" / "execution_path",
        ROOT / "afde" / "runtime_integration",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
            assert not {
                item for item in _imports(tree)
                if item.startswith(
                    "afde.production_adapter_availability"
                )
            }


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

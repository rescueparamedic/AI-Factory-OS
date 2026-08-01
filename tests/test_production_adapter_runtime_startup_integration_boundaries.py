import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTUP = ROOT / "afde" / "production_adapter_runtime_startup_integration"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.desktop",
    "afde.execution",
    "afde.product",
    "afde.providers",
    "cli",
    "dependency_injector",
    "httpx",
    "injector",
    "keyring",
    "oauthlib",
    "pluggy",
    "punq",
    "requests",
    "socket",
    "stevedore",
    "subprocess",
    "worker_runtime",
    "workers",
}


def test_startup_package_has_only_foundation_dependencies():
    imports = set()
    for path in STARTUP.glob("*.py"):
        imports.update(_imports(ast.parse(path.read_text(encoding="utf-8"))))

    assert {
        "afde.production_adapter_availability",
        "afde.production_adapter_creation",
        "afde.production_adapter_credential_readiness",
        "afde.production_adapter_discovery",
        "afde.production_adapter_invocation",
        "afde.production_composition",
    }.issubset(imports)
    assert not {
        item
        for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }


def test_startup_builder_never_creates_invokes_or_starts_behavior():
    tree = ast.parse(
        (STARTUP / "factory.py").read_text(encoding="utf-8")
    )
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not called_attributes.intersection(
        {"create", "invoke", "execute", "run", "start", "connect", "dispatch"}
    )


def test_protected_application_and_runtime_layers_do_not_import_startup_package():
    protected = (
        ROOT / "afde" / "desktop",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "runtime",
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
                if item.startswith(
                    "afde.production_adapter_runtime_startup_integration"
                )
            }


def test_startup_package_has_no_global_mutable_registry():
    for path in STARTUP.glob("*.py"):
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

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "afde" / "production_adapter_credential_readiness"
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
    "cryptography",
    "dotenv",
    "keyring",
    "oauthlib",
    "os",
    "requests",
    "runtime",
    "socket",
    "subprocess",
    "worker_runtime",
    "workers",
}
FORBIDDEN_CALLS = {
    "bind",
    "dispatch",
    "execute",
    "getenv",
    "health_check",
    "invoke",
    "load",
    "open",
    "probe",
    "run",
    "start",
}
FORBIDDEN_FIELD_NAMES = {
    "access_token",
    "api_key",
    "client_secret",
    "credential_value",
    "password",
    "private_key",
    "refresh_token",
    "secret_material",
    "secret_value",
}


def test_package_has_only_descriptor_metadata_dependencies():
    imports = set()
    calls = set()
    attributes = set()
    annotated_fields = set()
    for path in READINESS.glob("*.py"):
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
        annotated_fields.update(
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
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
    assert not annotated_fields.intersection(FORBIDDEN_FIELD_NAMES)


def test_package_has_no_environment_store_provider_or_logging_access():
    forbidden_attributes = {
        "environ",
        "get_credential",
        "get_password",
        "get_secret",
        "log",
        "logger",
        "read",
        "set_password",
        "write",
    }
    for path in READINESS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        assert not attributes.intersection(forbidden_attributes)


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
                    "afde.production_adapter_credential_readiness"
                )
            }


def test_protected_adapter_and_runtime_sources_do_not_import_package():
    protected = (
        ROOT / "afde" / "operational_adapter_registry",
        ROOT / "afde" / "production_adapter_availability",
        ROOT / "afde" / "production_adapter_discovery",
        ROOT / "afde" / "production_adapter_registration",
        ROOT / "afde" / "production_composition",
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
                    "afde.production_adapter_credential_readiness"
                )
            }


def test_package_exposes_no_forbidden_behavior_or_mutable_global():
    forbidden_methods = {
        "bind",
        "dispatch",
        "execute",
        "health_check",
        "invoke",
        "probe",
        "run",
        "start",
    }
    for path in READINESS.glob("*.py"):
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
                if names in (
                    ["__all__"],
                    ["EVIDENCE_REFERENCE_PATTERN"],
                ):
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

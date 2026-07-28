import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CREATION = ROOT / "afde" / "production_adapter_creation"
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
    "dependency_injector",
    "httpx",
    "injector",
    "keyring",
    "oauthlib",
    "os",
    "pluggy",
    "punq",
    "requests",
    "runtime",
    "socket",
    "stevedore",
    "subprocess",
    "worker_runtime",
    "workers",
}
FORBIDDEN_METHODS = {
    "bind",
    "call",
    "connect",
    "dispatch",
    "execute",
    "health_check",
    "invoke",
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


def test_package_has_only_approved_metadata_contract_dependencies():
    imports = set()
    annotated_fields = set()
    for path in CREATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports.update(_imports(tree))
        annotated_fields.update(
            node.target.id
            for node in ast.walk(tree)
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        )

    assert {
        "afde.tool_catalog",
        "afde.tool_adapter_contract",
        "afde.production_adapter_availability",
        "afde.production_adapter_credential_readiness",
    }.issubset(imports)
    assert not {
        item for item in imports
        if any(
            item == forbidden or item.startswith(f"{forbidden}.")
            for forbidden in FORBIDDEN_IMPORT_ROOTS
        )
    }
    assert not annotated_fields.intersection(FORBIDDEN_FIELD_NAMES)


def test_factory_and_instance_expose_no_execution_method():
    for path in CREATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        classes = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        for name in (
            "ProductionAdapterFactory",
            "ProductionAdapterInstance",
        ):
            node = classes.get(name)
            if node is None:
                continue
            methods = {
                item.name
                for item in node.body
                if isinstance(
                    item,
                    (ast.FunctionDef, ast.AsyncFunctionDef),
                )
            }
            assert not methods.intersection(FORBIDDEN_METHODS)


def test_package_has_no_environment_network_provider_or_logging_access():
    forbidden_attributes = {
        "environ",
        "get_credential",
        "get_password",
        "get_secret",
        "logger",
        "set_password",
    }
    for path in CREATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = _imports(tree)
        assert "logging" not in imports
        attributes = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        }
        assert not attributes.intersection(forbidden_attributes)


def test_protected_layers_do_not_import_creation_package():
    protected = (
        ROOT / "afde" / "operational_adapter_registry",
        ROOT / "afde" / "production_adapter_availability",
        ROOT / "afde" / "production_adapter_credential_readiness",
        ROOT / "afde" / "production_adapter_discovery",
        ROOT / "afde" / "production_adapter_registration",
        ROOT / "afde" / "production_composition",
        ROOT / "afde" / "tool_adapter_contract",
        ROOT / "afde" / "tool_catalog",
        ROOT / "afde" / "execution_path",
        ROOT / "afde" / "runtime_integration",
        ROOT / "real_worker_runtime",
        ROOT / "runtime",
        ROOT / "worker_runtime",
        ROOT / "workers",
        ROOT / "cli",
    )
    for directory in protected:
        for path in directory.glob("*.py"):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), filename=str(path),
            )
            assert not {
                item for item in _imports(tree)
                if item.startswith("afde.production_adapter_creation")
            }


def test_no_global_mutable_instance_registry_or_service_locator():
    for path in CREATION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = (
                    [target.id for target in node.targets]
                    if isinstance(node, ast.Assign)
                    else [node.target.id]
                )
                if names in (
                    ["__all__"],
                    ["CONFIGURATION_REFERENCE_PATTERN"],
                    ["CREATION_REFERENCE_PATTERN"],
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

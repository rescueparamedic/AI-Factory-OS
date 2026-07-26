import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_COMPOSITION = ROOT / "afde" / "production_composition"
FORBIDDEN_IMPORT_ROOTS = {
    "afde.execution",
    "afde.operator",
    "afde.product",
    "afde.providers",
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
    "cancel",
    "dispatch",
    "execute",
    "getenv",
    "import_module",
    "invoke",
    "load",
    "open",
    "read_bytes",
    "read_text",
    "recover",
    "resume",
    "run",
    "start",
    "write_bytes",
    "write_text",
}


def test_production_composition_has_no_execution_or_external_boundary():
    for path in PRODUCTION_COMPOSITION.glob("*.py"):
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


def test_existing_layers_do_not_reverse_import_production_composition():
    directories = (
        ROOT / "afde" / "execution_path",
        ROOT / "afde" / "non_executable_composition",
        ROOT / "afde" / "operational_adapter_registry",
        ROOT / "afde" / "operator",
        ROOT / "afde" / "planner_resolution",
        ROOT / "afde" / "product",
        ROOT / "afde" / "providers",
        ROOT / "afde" / "resolver",
        ROOT / "afde" / "runtime_integration",
        ROOT / "afde" / "tool_adapter_contract",
        ROOT / "afde" / "tool_catalog",
        ROOT / "afde" / "tool_selection",
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
                if item.startswith("afde.production_composition")
            }


def test_no_hidden_loading_runtime_construction_or_di_framework():
    forbidden_construction = {
        "DevelopmentRunService",
        "KnowledgeFoundationProvider",
        "OperatorService",
        "RealWorkerRuntime",
        "ToolAdapterCatalog",
    }
    forbidden_dynamic = {
        "__import__",
        "find_spec",
        "getenv",
        "import_module",
        "load",
        "load_module",
    }
    forbidden_dependencies = {
        "dependency_injector",
        "injector",
        "punq",
    }
    for path in PRODUCTION_COMPOSITION.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert not _imports(tree).intersection(forbidden_dependencies)
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = (
                    [target.id for target in node.targets]
                    if isinstance(node, ast.Assign)
                    else [node.target.id]
                )
                if names in (["__all__"], ["_KNOWLEDGE_PROVIDER_METHODS"]):
                    continue
                assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))
        constructed = {
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
        assert not constructed.intersection(forbidden_construction)
        assert not constructed.intersection(forbidden_dynamic)
        assert not attributes.intersection(forbidden_dynamic)


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

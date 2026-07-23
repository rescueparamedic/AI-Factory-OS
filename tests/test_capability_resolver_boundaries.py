import ast
from pathlib import Path

from afde.knowledge import KnowledgeFoundationProvider
from afde.resolver import CapabilityRequirement, CapabilityResolver


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "afde" / "resolver"
REGISTRY = (
    ROOT / "docs" / "registry" / "KNOWLEDGE_FOUNDATION_REGISTRY_v1.json"
)
SOURCE = ROOT / "docs" / "development" / "AFDE_ARCHITECTURE_v1.md"

FORBIDDEN_IMPORT_ROOTS = {
    "afde.cli",
    "afde.desktop",
    "afde.execution",
    "afde.operator",
    "afde.planner",
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


def test_resolver_has_no_forbidden_import_or_io_boundary():
    for path in RESOLVER.glob("*.py"):
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


def test_resolution_does_not_change_registry_or_source_bytes():
    registry_before = REGISTRY.read_bytes()
    source_before = SOURCE.read_bytes()

    resolver = CapabilityResolver(KnowledgeFoundationProvider(ROOT))
    resolver.resolve(CapabilityRequirement(capability_id="CAP-KNOW-0001"))

    assert REGISTRY.read_bytes() == registry_before
    assert SOURCE.read_bytes() == source_before


def _imports(tree):
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result

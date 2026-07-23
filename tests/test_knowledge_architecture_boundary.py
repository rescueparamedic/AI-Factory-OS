import ast
from pathlib import Path

from afde.knowledge import KnowledgeFoundationProvider


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "afde" / "knowledge"
FORBIDDEN_IMPORTS = (
    "real_worker_runtime",
    "afde.product",
    "afde.planner",
    "afde.execution",
    "afde.operator",
    "afde.providers",
)
NETWORK_IMPORTS = ("socket", "urllib", "http", "requests", "openai")


def _imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return tuple(names)


def test_knowledge_package_has_no_forbidden_or_network_imports():
    imports = tuple(
        name
        for path in PACKAGE.glob("*.py")
        for name in _imports(path)
    )

    assert not any(
        name == blocked or name.startswith(f"{blocked}.")
        for name in imports
        for blocked in FORBIDDEN_IMPORTS + NETWORK_IMPORTS
    )


def test_knowledge_package_has_no_execution_or_write_boundary():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in PACKAGE.glob("*.py")
    )

    for token in (
        "subprocess",
        "write_text(",
        "write_bytes(",
        "urlopen(",
        "requests.",
        "socket.",
        "rglob(",
        "*.md",
    ):
        assert token not in source


def test_provider_reads_only_the_governed_json_snapshot():
    registry = (
        ROOT / "docs" / "registry" / "KNOWLEDGE_FOUNDATION_REGISTRY_v1.json"
    )
    markdown = ROOT / "docs" / "standards" / "KNOWLEDGE_REGISTRY_STANDARD_v1.md"
    registry_before = registry.read_bytes()
    markdown_before = markdown.read_bytes()

    provider = KnowledgeFoundationProvider(ROOT)
    provider.capability_context("CAP-KNOW-0001")

    assert registry.read_bytes() == registry_before
    assert markdown.read_bytes() == markdown_before

from inspect import Parameter, signature

from afde.production_adapter_discovery import (
    build_discovered_production_adapter_registry,
)
from afde.production_adapter_runtime_startup_integration import (
    build_production_adapter_runtime_startup_composition,
)
from afde.production_composition import build_production_composition


def test_existing_builder_signatures_remain_unchanged():
    discovery = signature(build_discovered_production_adapter_registry)
    assert str(discovery) == (
        "(*, source: 'ProductionAdapterDiscoverySource | None' = None) "
        "-> 'OperationalAdapterRegistry'"
    )
    composition = signature(build_production_composition)
    assert tuple(composition.parameters) == (
        "knowledge_provider",
        "adapter_registry",
        "runtime_policy",
    )
    assert all(
        parameter.kind is Parameter.KEYWORD_ONLY
        for parameter in composition.parameters.values()
    )


def test_startup_builder_requires_only_explicit_keyword_dependencies():
    parameters = signature(
        build_production_adapter_runtime_startup_composition
    ).parameters
    assert tuple(parameters) == (
        "knowledge_provider",
        "runtime_policy",
        "adapter_id",
        "discovery_source",
        "factory",
        "credential_readiness_evidence",
        "configuration_metadata",
        "invocation_target",
    )
    assert all(item.kind is Parameter.KEYWORD_ONLY for item in parameters.values())
    assert all(item.default is Parameter.empty for item in parameters.values())

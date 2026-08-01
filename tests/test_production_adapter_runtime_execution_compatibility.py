from inspect import Parameter, signature

from afde.production_adapter_invocation import InvocationService
from afde.production_adapter_runtime_execution import (
    ProductionAdapterRuntimeExecutionService,
)
from afde.production_adapter_runtime_startup_integration import (
    build_production_adapter_runtime_startup_composition,
)


def test_existing_startup_builder_public_signature_remains_unchanged():
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


def test_existing_invocation_and_new_execution_signatures_are_separate():
    invocation = signature(InvocationService.invoke)
    assert tuple(invocation.parameters) == ("self", "request", "target")

    execution = signature(ProductionAdapterRuntimeExecutionService.execute)
    assert tuple(execution.parameters) == ("self", "request")

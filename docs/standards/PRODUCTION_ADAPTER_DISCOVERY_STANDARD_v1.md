# Production Adapter Discovery Standard v1

## Status

- Standard ID: `DOC-PADDISC-0001`
- Status: Active
- Owner: AI Factory OS Architecture
- Effective Sprint: AFDE-6.0
- Capability: `CAP-PRODUCTIONADAPTERDISCOVERY-0001`

## Purpose and Ownership

Production Adapter Discovery is a metadata-only foundation for installed Tool
Adapter descriptors. It queries the exact Python entry-point group
`ai_factory_os.tool_adapters` through a single injectable discovery-source
boundary and requires each entry point to load exactly one existing
`ToolAdapterDescriptor`.

The default source uses only Python standard-library `importlib.metadata`.
Tests inject fake discovery sources and require no package installation.
Discovery does not scan filesystems or namespace packages and introduces no
plugin framework or dependency-injection container.

## Discovery and Registry Flow

```text
ImportlibMetadataDiscoverySource or caller-injected fake source
        |
        v
ai_factory_os.tool_adapters entry-point metadata
        |
        v
existing ToolAdapterDescriptor values
        |
        + static production registration descriptors
        |
        v
existing OperationalAdapterRegistry
        |
        v
existing ToolAdapterCatalog
```

`discover_production_adapter_descriptors()` deterministically orders entry
points by metadata name and value and loads each descriptor once.
`build_discovered_production_adapter_registry()` merges the resulting
descriptors with the unchanged static result of
`build_production_adapter_registry()`. The existing Registry and Catalog own
descriptor validation, deterministic ordering, duplicate identity rejection,
Capability mapping, and selectable-capability ambiguity rejection.

The existing `build_production_adapter_registry()` and
`build_production_composition()` signatures and behavior remain unchanged.
The discovered Registry remains directly compatible with the existing
production composition and supplies the same Catalog instance to downstream
services.

## Fail-closed Policy

- discovery-source enumeration failure raises `DiscoverySourceError`;
- entry-point load failure raises `EntryPointLoadError`;
- a loaded value that is not one `ToolAdapterDescriptor` raises
  `EntryPointTypeError`;
- duplicate adapter identity continues to raise the existing
  `DuplicateAdapterIdentityError`;
- selectable Capability ambiguity continues to raise the existing
  `AmbiguousCapabilityMappingError`.

Discovery does not recover, skip, coerce, instantiate, bind, invoke, execute,
health-check, network-probe, or inspect credentials. Descriptor availability,
compatibility, execution-contract, privacy, cost, and credential fields remain
declared metadata and do not establish operational truth.

## Authority and Isolation

This capability adds no Runtime startup, lifecycle, Worker, Provider, CLI,
Desktop, hot reload, application wiring, network, filesystem scan, namespace
scan, credential handling, Adapter binding, or Adapter invocation behavior.
It does not add Pluggy, Stevedore, a DI container, or another descriptor,
Registry, or Catalog model.

Composition continues to keep:

- `runtime_allowed: false`
- `execution_allowed: false`

## Capability Registration

```yaml
capability_id: CAP-PRODUCTIONADAPTERDISCOVERY-0001
status: implemented
maturity: M3
implementation_status: implemented
required_capabilities:
  - CAP-PRODUCTIONADAPTERREGISTRATION-0001
  - CAP-ADAPTERREGISTRY-0001
```

Operational Evidence, Adapter execution and binding, Runtime integration, hot
reload, and M4 validation remain outside this foundation.

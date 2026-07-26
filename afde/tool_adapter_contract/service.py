"""Deterministic non-executable Tool Adapter binding validation."""
from __future__ import annotations

from hashlib import sha256
from typing import Iterable, Protocol

from afde.tool_catalog import ToolAdapterDescriptor

from .errors import InvalidToolAdapterRequestError
from .models import (
    ToolAdapterBinding,
    ToolAdapterContractStatus,
    ToolAdapterError,
    ToolAdapterErrorCode,
    ToolAdapterRequest,
    ToolAdapterResult,
)


class AdapterLookup(Protocol):
    """Read-only injected boundary for adapter descriptor snapshots."""

    def list_adapters(self) -> Iterable[ToolAdapterDescriptor]: ...


class ToolAdapterContractService:
    """Validate a Runtime Projection against adapter metadata without invoking it."""

    def __init__(self, lookup: AdapterLookup) -> None:
        if not callable(getattr(lookup, "list_adapters", None)):
            raise TypeError("lookup must provide list_adapters()")
        self._lookup = lookup

    def bind(self, request: ToolAdapterRequest) -> ToolAdapterResult:
        """Return exact binding metadata or structured fail-closed errors."""

        if not isinstance(request, ToolAdapterRequest):
            raise InvalidToolAdapterRequestError(
                "request must be a ToolAdapterRequest"
            )
        projection = request.projection
        if projection.runtime_allowed or projection.execution_allowed:
            raise InvalidToolAdapterRequestError(
                "Runtime projection cannot grant execution authority"
            )

        descriptors, error = self._snapshot(request)
        if error is not None:
            return self._rejected(
                request,
                (error,),
                (
                    f"01.request.accepted:{request.projection_id}",
                    f"02.lookup.rejected:{error.code.value}",
                    "03.binding.rejected",
                ),
            )

        identities = tuple(item.adapter_id for item in descriptors)
        duplicates = tuple(sorted({
            identity for identity in identities
            if identities.count(identity) > 1
        }))
        if duplicates:
            duplicate = self._error(
                request,
                ToolAdapterErrorCode.DUPLICATE,
                "duplicate adapter identities: " + ",".join(duplicates),
            )
            return self._rejected(
                request,
                (duplicate,),
                (
                    f"01.request.accepted:{request.projection_id}",
                    f"02.lookup.snapshot:{len(descriptors)}",
                    "03.lookup.duplicate:" + ",".join(duplicates),
                    "04.binding.rejected",
                ),
            )

        matches = tuple(
            item for item in descriptors
            if item.adapter_id == request.adapter_id
        )
        if not matches:
            unregistered = self._error(
                request,
                ToolAdapterErrorCode.UNREGISTERED,
                f"adapter is not registered: {request.adapter_id}",
            )
            return self._rejected(
                request,
                (unregistered,),
                (
                    f"01.request.accepted:{request.projection_id}",
                    f"02.lookup.snapshot:{len(descriptors)}",
                    f"03.adapter.unregistered:{request.adapter_id}",
                    "04.binding.rejected",
                ),
            )

        descriptor = matches[0]
        mismatches = self._mismatches(projection, descriptor)
        if mismatches:
            mismatch = self._error(
                request,
                ToolAdapterErrorCode.MISMATCH,
                "adapter binding mismatch: " + ",".join(mismatches),
            )
            return self._rejected(
                request,
                (mismatch,),
                (
                    f"01.request.accepted:{request.projection_id}",
                    f"02.lookup.snapshot:{len(descriptors)}",
                    f"03.adapter.found:{request.adapter_id}",
                    "04.adapter.mismatch:" + ",".join(mismatches),
                    "05.binding.rejected",
                ),
            )

        binding_id = self._binding_id(request, descriptor)
        binding = ToolAdapterBinding(
            binding_id=binding_id,
            projection_id=request.projection_id,
            path_id=request.path_id,
            capability_id=request.capability_id,
            adapter_id=request.adapter_id,
            adapter_version=descriptor.version,
            descriptor=descriptor,
            runtime_allowed=False,
            execution_allowed=False,
        )
        return ToolAdapterResult(
            status=ToolAdapterContractStatus.VALIDATED,
            projection_id=request.projection_id,
            path_id=request.path_id,
            capability_id=request.capability_id,
            adapter_id=request.adapter_id,
            binding=binding,
            errors=(),
            trace=(
                f"01.request.accepted:{request.projection_id}",
                f"02.lookup.snapshot:{len(descriptors)}",
                f"03.adapter.found:{request.adapter_id}",
                "04.adapter.identity.validated",
                f"05.binding.validated:{binding_id}",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )

    def _snapshot(
        self, request: ToolAdapterRequest,
    ) -> tuple[tuple[ToolAdapterDescriptor, ...], ToolAdapterError | None]:
        try:
            values = self._lookup.list_adapters()
            if isinstance(values, (str, bytes)):
                raise TypeError
            snapshot = tuple(values)
        except Exception:
            return (), self._error(
                request,
                ToolAdapterErrorCode.MALFORMED,
                "adapter lookup did not provide an iterable snapshot",
            )
        if any(
            not isinstance(item, ToolAdapterDescriptor)
            for item in snapshot
        ):
            return (), self._error(
                request,
                ToolAdapterErrorCode.MALFORMED,
                "adapter lookup contains malformed metadata",
            )
        try:
            for item in snapshot:
                ToolAdapterDescriptor(
                    adapter_id=item.adapter_id,
                    display_name=item.display_name,
                    version=item.version,
                    supported_capability_ids=item.supported_capability_ids,
                    availability=item.availability,
                    runtime_compatibility=item.runtime_compatibility,
                    execution_contract=item.execution_contract,
                    privacy_classification=item.privacy_classification,
                    cost_classification=item.cost_classification,
                    credentials_required=item.credentials_required,
                    description=item.description,
                    metadata_references=item.metadata_references,
                )
            ordered = tuple(sorted(
                snapshot, key=lambda item: item.adapter_id,
            ))
        except Exception:
            return (), self._error(
                request,
                ToolAdapterErrorCode.MALFORMED,
                "adapter lookup contains malformed metadata",
            )
        return ordered, None

    @staticmethod
    def _mismatches(projection, descriptor) -> tuple[str, ...]:
        checks = (
            (
                "capability_id",
                projection.capability_id
                not in descriptor.supported_capability_ids,
            ),
            ("adapter_version", projection.adapter_version != descriptor.version),
            ("availability", projection.availability is not descriptor.availability),
            (
                "runtime_compatibility",
                projection.runtime_compatibility
                is not descriptor.runtime_compatibility,
            ),
            (
                "execution_contract",
                projection.execution_contract is not descriptor.execution_contract,
            ),
            (
                "privacy_classification",
                projection.privacy_classification
                is not descriptor.privacy_classification,
            ),
            (
                "cost_classification",
                projection.cost_classification
                is not descriptor.cost_classification,
            ),
            (
                "credentials_required",
                projection.credentials_required
                is not descriptor.credentials_required,
            ),
            (
                "metadata_references",
                projection.metadata_references != descriptor.metadata_references,
            ),
        )
        return tuple(name for name, mismatched in checks if mismatched)

    @staticmethod
    def _binding_id(
        request: ToolAdapterRequest,
        descriptor: ToolAdapterDescriptor,
    ) -> str:
        parts = (
            request.projection_id,
            request.path_id,
            request.capability_id,
            request.adapter_id,
            descriptor.version,
            *descriptor.supported_capability_ids,
            descriptor.availability.value,
            descriptor.runtime_compatibility.value,
            descriptor.execution_contract.value,
            descriptor.privacy_classification.value,
            descriptor.cost_classification.value,
            str(descriptor.credentials_required).lower(),
            *descriptor.metadata_references,
        )
        digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return f"ADAPTERBIND-{digest[:16].upper()}"

    @staticmethod
    def _error(
        request: ToolAdapterRequest,
        code: ToolAdapterErrorCode,
        message: str,
    ) -> ToolAdapterError:
        return ToolAdapterError(
            code=code,
            message=message,
            projection_id=request.projection_id,
            path_id=request.path_id,
            capability_id=request.capability_id,
            adapter_id=request.adapter_id,
            runtime_allowed=False,
            execution_allowed=False,
        )

    @staticmethod
    def _rejected(
        request: ToolAdapterRequest,
        errors: tuple[ToolAdapterError, ...],
        trace: tuple[str, ...],
    ) -> ToolAdapterResult:
        return ToolAdapterResult(
            status=ToolAdapterContractStatus.REJECTED,
            projection_id=request.projection_id,
            path_id=request.path_id,
            capability_id=request.capability_id,
            adapter_id=request.adapter_id,
            binding=None,
            errors=errors,
            trace=trace,
            runtime_allowed=False,
            execution_allowed=False,
        )

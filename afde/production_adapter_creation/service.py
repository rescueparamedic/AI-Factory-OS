"""Explicit factory boundary for inert production adapter creation."""
from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

from afde.production_adapter_credential_readiness import (
    CredentialReadinessStatus,
)

from .errors import (
    AdapterUnavailableForCreationError,
    CredentialNotReadyForCreationError,
    DuplicateProductionAdapterFactoryError,
    InvalidProductionAdapterCreationContextError,
    InvalidProductionAdapterFactoryError,
    InvalidProductionAdapterInstanceError,
    ProductionAdapterCreationIdentityMismatchError,
    ProductionAdapterFactoryCreationError,
    ProductionAdapterFactoryNotFoundError,
)
from .models import (
    ProductionAdapterCreationContext,
    ProductionAdapterCreationResult,
    ProductionAdapterFactory,
    ProductionAdapterInstance,
)


class ProductionAdapterCreationService:
    """Validate explicit factories and create inert adapter instances."""

    def __init__(
        self,
        factories: Iterable[ProductionAdapterFactory],
    ) -> None:
        try:
            supplied = tuple(factories)
        except Exception as exc:
            raise InvalidProductionAdapterFactoryError(
                "factories must be an iterable"
            ) from exc
        registrations = []
        for factory in supplied:
            adapter_id = getattr(factory, "adapter_id", None)
            if (
                not isinstance(adapter_id, str)
                or not adapter_id
                or adapter_id != adapter_id.strip()
                or not callable(getattr(factory, "create", None))
            ):
                raise InvalidProductionAdapterFactoryError(
                    "factory must declare an exact adapter identity and "
                    "create method"
                )
            registrations.append((adapter_id, factory))
        ordered = tuple(sorted(
            registrations,
            key=lambda item: item[0],
        ))
        identities = tuple(item[0] for item in ordered)
        if len(identities) != len(set(identities)):
            raise DuplicateProductionAdapterFactoryError(
                "factory registrations contain duplicate identities"
            )
        self._factory_ids = identities
        self._factories = MappingProxyType(dict(ordered))

    @property
    def factory_ids(self) -> tuple[str, ...]:
        """Return the deterministic immutable factory identity snapshot."""

        return self._factory_ids

    def create(
        self,
        context: ProductionAdapterCreationContext,
    ) -> ProductionAdapterCreationResult:
        """Create one inert instance after all metadata preconditions pass."""

        if type(context) is not ProductionAdapterCreationContext:
            raise InvalidProductionAdapterCreationContextError(
                "context must be ProductionAdapterCreationContext"
            )
        if not context.availability.available:
            raise AdapterUnavailableForCreationError(
                "adapter availability does not permit creation"
            )
        expected_readiness = (
            CredentialReadinessStatus.READY
            if context.descriptor.credentials_required
            else CredentialReadinessStatus.NOT_REQUIRED
        )
        if context.credential_readiness.status is not expected_readiness:
            raise CredentialNotReadyForCreationError(
                "credential readiness does not permit creation"
            )
        try:
            factory = self._factories[context.adapter_id]
        except KeyError as exc:
            raise ProductionAdapterFactoryNotFoundError(
                "no factory is registered for the adapter identity"
            ) from exc
        if factory.adapter_id != context.descriptor.adapter_id:
            raise ProductionAdapterCreationIdentityMismatchError(
                "factory identity conflicts with descriptor"
            )
        try:
            instance = factory.create(context)
        except Exception as exc:
            raise ProductionAdapterFactoryCreationError(
                "factory could not create an adapter instance"
            ) from exc
        if type(instance) is not ProductionAdapterInstance:
            raise InvalidProductionAdapterInstanceError(
                "factory must return exactly one ProductionAdapterInstance"
            )
        if instance.adapter_id != context.adapter_id:
            raise ProductionAdapterCreationIdentityMismatchError(
                "factory instance identity conflicts with descriptor"
            )
        return ProductionAdapterCreationResult(
            context=context,
            instance=instance,
            factory_adapter_id=factory.adapter_id,
            trace=(
                f"01.context.accepted:{context.adapter_id}",
                "02.availability.accepted",
                "03.credential_readiness.accepted",
                "04.factory.resolved",
                "05.instance.created",
                "06.authority.denied",
            ),
            runtime_allowed=False,
            execution_allowed=False,
        )

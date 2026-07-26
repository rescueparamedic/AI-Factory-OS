"""Deterministic front door for explicitly supplied adapter registrations."""
from __future__ import annotations

from collections.abc import Iterable

from afde.tool_catalog import (
    InvalidToolAdapterCatalogError,
    ToolAdapterCatalog,
    ToolAdapterCatalogSnapshot,
    ToolAdapterDescriptor,
)


class OperationalAdapterRegistry:
    """Validate explicit registrations and project the existing Catalog."""

    def __init__(
        self,
        registrations: Iterable[ToolAdapterDescriptor],
    ) -> None:
        try:
            supplied = tuple(registrations)
        except Exception as exc:
            raise InvalidToolAdapterCatalogError(
                "operational registrations must be an iterable"
            ) from exc
        if any(
            not isinstance(item, ToolAdapterDescriptor)
            for item in supplied
        ):
            raise InvalidToolAdapterCatalogError(
                "operational registrations contain malformed metadata"
            )

        self._catalog = ToolAdapterCatalog(supplied)

    @property
    def snapshot(self) -> ToolAdapterCatalogSnapshot:
        """Return the existing immutable deterministic Catalog snapshot."""

        return self._catalog.snapshot

    def project_catalog(self) -> ToolAdapterCatalog:
        """Return the single validated Catalog for downstream services."""

        return self._catalog

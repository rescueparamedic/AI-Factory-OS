"""Structural metadata boundaries for production adapter discovery."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class ProductionAdapterEntryPoint(Protocol):
    """Minimal loadable entry-point metadata used by discovery."""

    @property
    def name(self) -> str: ...

    @property
    def value(self) -> str: ...

    def load(self) -> object: ...


class ProductionAdapterDiscoverySource(Protocol):
    """Injectable source of Tool Adapter descriptor entry points."""

    def entry_points(
        self,
        group: str,
    ) -> Iterable[ProductionAdapterEntryPoint]: ...

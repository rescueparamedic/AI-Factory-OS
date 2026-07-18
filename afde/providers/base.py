"""Minimal provider interface used by AFDE product integrations."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import ProviderResponse


class AIProvider(ABC):
    @abstractmethod
    def generate(self, request: str) -> ProviderResponse:
        """Generate one response without performing local actions."""
        raise NotImplementedError

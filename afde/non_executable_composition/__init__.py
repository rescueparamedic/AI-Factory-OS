"""Additive public contract for non-executable capability composition."""

from .factory import build_non_executable_composition
from .models import NonExecutableComposition

__all__ = [
    "NonExecutableComposition",
    "build_non_executable_composition",
]

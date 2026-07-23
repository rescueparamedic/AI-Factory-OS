"""Fail-closed Knowledge Foundation errors."""


class KnowledgeFoundationError(RuntimeError):
    """Base error for Knowledge Foundation operations."""


class RegistryLoadError(KnowledgeFoundationError):
    """The registry snapshot could not be read or decoded."""


class RegistryNotFoundError(RegistryLoadError):
    """The configured registry snapshot does not exist."""


class RegistryPathError(RegistryLoadError):
    """The configured registry path escapes the repository boundary."""


class RegistryValidationError(KnowledgeFoundationError):
    """The registry snapshot violates its governed schema."""

    def __init__(self, errors: list[str] | tuple[str, ...]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


class RegistryLookupError(KnowledgeFoundationError, LookupError):
    """A requested registered identifier does not exist."""

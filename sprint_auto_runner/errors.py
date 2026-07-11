class SprintRunnerError(Exception):
    """Base Sprint Auto Runner error."""


class SprintDefinitionError(SprintRunnerError):
    """Sprint definition is malformed or unsafe."""


class SprintStateError(SprintRunnerError):
    """Persisted run state is missing, corrupt, or inconsistent."""


class SprintResumeError(SprintRunnerError):
    """A run cannot be resumed with the supplied approval."""

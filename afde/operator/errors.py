"""Stable operator-boundary errors and exit codes."""


class OperatorError(RuntimeError):
    exit_code = 5


class OperatorInputError(OperatorError, ValueError):
    exit_code = 2


class OperatorPreflightBlocked(OperatorError):
    exit_code = 3


class OperatorNotFound(OperatorError):
    exit_code = 4


class OperatorExecutionFailed(OperatorError):
    exit_code = 5

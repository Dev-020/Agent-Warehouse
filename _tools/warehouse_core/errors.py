"""Exceptions carrying exit codes (DESIGN §1, §4)."""


class WarehouseError(Exception):
    code = 1


class UsageError(WarehouseError):
    """Bad arguments, invalid manifest/config, unknown id."""
    code = 2


class GitError(WarehouseError):
    """Git failure, missing tag, not a repo, busy run lock."""
    code = 3


class ConflictError(WarehouseError):
    code = 4


class ReleaseCheckError(WarehouseError):
    code = 5


class ConfirmationRequired(WarehouseError):
    code = 10


class GuardError(WarehouseError):
    """A write outside the allowed paths was attempted (invariant I1). Reported per item, never ignored."""
    code = 1

"""Identity and Access infrastructure adapters."""

from extensible_ai_workspace.identity.infrastructure.postgres import (
    IdentityPersistenceConflict,
    IdentityPersistenceError,
    IdentityRecordNotFound,
    PostgresIdentityRepository,
    PostgresIdentityUnitOfWork,
)

__all__ = [
    "IdentityPersistenceConflict",
    "IdentityPersistenceError",
    "IdentityRecordNotFound",
    "PostgresIdentityRepository",
    "PostgresIdentityUnitOfWork",
]

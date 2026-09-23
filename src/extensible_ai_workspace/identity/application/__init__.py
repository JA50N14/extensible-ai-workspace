"""Identity and Access application boundary."""

from extensible_ai_workspace.identity.application.errors import (
    AuthenticationError,
    InactiveIdentity,
    InvalidCsrfToken,
    InvalidSession,
)
from extensible_ai_workspace.identity.application.ports import (
    IdentityRepository,
    IdentityUnitOfWork,
    IdentityUnitOfWorkFactory,
)
from extensible_ai_workspace.identity.application.sessions import (
    AuthenticatedSession,
    EstablishedSession,
    TrustedLocalIdentity,
    TrustedLocalSessionService,
)

__all__ = [
    "AuthenticatedSession",
    "AuthenticationError",
    "EstablishedSession",
    "IdentityRepository",
    "IdentityUnitOfWork",
    "IdentityUnitOfWorkFactory",
    "InactiveIdentity",
    "InvalidCsrfToken",
    "InvalidSession",
    "TrustedLocalIdentity",
    "TrustedLocalSessionService",
]

"""Application ports required by Identity and Access use cases."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol
from uuid import UUID

from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
    ExternalIdentity,
    IdentityProviderType,
    InternalUser,
)


class IdentityRepository(Protocol):
    """Persistence operations required by identity and session use cases."""

    def get_user(
        self,
        user_id: UUID,
    ) -> InternalUser | None:
        """Return an internal user by identifier."""

        ...

    def add_user(
        self,
        user: InternalUser,
    ) -> None:
        """Persist a new internal user."""

        ...

    def get_external_identity(
        self,
        *,
        provider_type: IdentityProviderType,
        issuer: str,
        subject: str,
    ) -> ExternalIdentity | None:
        """Return the matching external identity mapping."""

        ...

    def add_external_identity(
        self,
        identity: ExternalIdentity,
    ) -> None:
        """Persist a new external identity mapping."""

        ...

    def add_session(
        self,
        session: ApplicationSession,
    ) -> None:
        """Persist a new server-side application session."""

        ...

    def get_session_by_token_hash(
        self,
        session_token_hash: bytes,
    ) -> ApplicationSession | None:
        """Return the session matching a stored token hash."""

        ...

    def update_session(
        self,
        session: ApplicationSession,
    ) -> None:
        """Persist the current state of an existing session."""

        ...


class IdentityUnitOfWork(Protocol):
    """Transaction boundary for Identity and Access use cases."""

    identities: IdentityRepository

    def __enter__(self) -> "IdentityUnitOfWork":
        """Enter the transaction boundary."""

        ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the transaction and release its resources."""

        ...

    def commit(self) -> None:
        """Commit all changes performed inside this unit of work."""

        ...

    def rollback(self) -> None:
        """Discard all uncommitted changes."""

        ...


IdentityUnitOfWorkFactory = Callable[[], IdentityUnitOfWork]

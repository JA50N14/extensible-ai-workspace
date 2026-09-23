"""PostgreSQL persistence for Identity and Access."""

from types import TracebackType
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
    AuthenticationMethod,
    ExternalIdentity,
    IdentityProviderType,
    InternalUser,
    UserStatus,
)


class IdentityPersistenceError(RuntimeError):
    """Base failure raised by Identity and Access persistence."""


class IdentityPersistenceConflict(IdentityPersistenceError):
    """A persisted uniqueness or integrity rule was violated."""


class IdentityRecordNotFound(IdentityPersistenceError):
    """A requested persisted record does not exist."""


class PostgresIdentityRepository:
    """Persist Identity and Access domain objects in PostgreSQL."""

    def __init__(
        self,
        connection: Connection[dict[str, Any]],
    ) -> None:
        self._connection = connection

    def get_user(
        self,
        user_id: UUID,
    ) -> InternalUser | None:
        """Return an internal user by identifier."""

        try:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    status,
                    display_name,
                    primary_email,
                    created_at,
                    updated_at,
                    disabled_at,
                    deletion_requested_at,
                    version
                FROM iam.users
                WHERE id = %s
                """,
                (user_id,),
            ).fetchone()
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to load the internal user."
            ) from error

        if row is None:
            return None

        return _map_user(row)

    def add_user(
        self,
        user: InternalUser,
    ) -> None:
        """Persist a new internal user."""

        try:
            self._connection.execute(
                """
                INSERT INTO iam.users (
                    id,
                    status,
                    display_name,
                    primary_email,
                    created_at,
                    updated_at,
                    disabled_at,
                    deletion_requested_at,
                    version
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    user.id,
                    user.status.value,
                    user.display_name,
                    user.primary_email,
                    user.created_at,
                    user.updated_at,
                    user.disabled_at,
                    user.deletion_requested_at,
                    user.version,
                ),
            )
        except psycopg.IntegrityError as error:
            raise IdentityPersistenceConflict(
                "The internal user conflicts with persisted data."
            ) from error
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to persist the internal user."
            ) from error

    def get_external_identity(
        self,
        *,
        provider_type: IdentityProviderType,
        issuer: str,
        subject: str,
    ) -> ExternalIdentity | None:
        """Return the matching external identity mapping."""

        try:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    provider_type,
                    issuer,
                    subject,
                    created_at,
                    last_authenticated_at,
                    disabled_at,
                    claims_profile_version
                FROM iam.external_identities
                WHERE provider_type = %s
                  AND issuer = %s
                  AND subject = %s
                """,
                (
                    provider_type.value,
                    issuer,
                    subject,
                ),
            ).fetchone()
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to load the external identity."
            ) from error

        if row is None:
            return None

        return _map_external_identity(row)

    def add_external_identity(
        self,
        identity: ExternalIdentity,
    ) -> None:
        """Persist a new external identity mapping."""

        try:
            self._connection.execute(
                """
                INSERT INTO iam.external_identities (
                    id,
                    user_id,
                    provider_type,
                    issuer,
                    subject,
                    created_at,
                    last_authenticated_at,
                    disabled_at,
                    claims_profile_version
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    identity.id,
                    identity.user_id,
                    identity.provider_type.value,
                    identity.issuer,
                    identity.subject,
                    identity.created_at,
                    identity.last_authenticated_at,
                    identity.disabled_at,
                    identity.claims_profile_version,
                ),
            )
        except psycopg.IntegrityError as error:
            raise IdentityPersistenceConflict(
                "The external identity conflicts with persisted data."
            ) from error
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to persist the external identity."
            ) from error

    def add_session(
        self,
        session: ApplicationSession,
    ) -> None:
        """Persist a new server-side application session."""

        try:
            self._connection.execute(
                """
                INSERT INTO iam.sessions (
                    id,
                    user_id,
                    external_identity_id,
                    authentication_method,
                    session_token_hash,
                    csrf_verifier,
                    created_at,
                    last_activity_at,
                    idle_expires_at,
                    absolute_expires_at,
                    revoked_at,
                    revocation_reason,
                    authenticated_at,
                    rotation_generation,
                    security_context_version
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    session.id,
                    session.user_id,
                    session.external_identity_id,
                    session.authentication_method.value,
                    session.session_token_hash,
                    session.csrf_verifier,
                    session.created_at,
                    session.last_activity_at,
                    session.idle_expires_at,
                    session.absolute_expires_at,
                    session.revoked_at,
                    session.revocation_reason,
                    session.authenticated_at,
                    session.rotation_generation,
                    session.security_context_version,
                ),
            )
        except psycopg.IntegrityError as error:
            raise IdentityPersistenceConflict(
                "The application session conflicts with persisted data."
            ) from error
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to persist the application session."
            ) from error

    def get_session_by_token_hash(
        self,
        session_token_hash: bytes,
    ) -> ApplicationSession | None:
        """Return the session matching a stored token hash."""

        try:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    user_id,
                    external_identity_id,
                    authentication_method,
                    session_token_hash,
                    csrf_verifier,
                    created_at,
                    last_activity_at,
                    idle_expires_at,
                    absolute_expires_at,
                    revoked_at,
                    revocation_reason,
                    authenticated_at,
                    rotation_generation,
                    security_context_version
                FROM iam.sessions
                WHERE session_token_hash = %s
                """,
                (session_token_hash,),
            ).fetchone()
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to load the application session."
            ) from error

        if row is None:
            return None

        return _map_session(row)

    def update_session(
        self,
        session: ApplicationSession,
    ) -> None:
        """Persist the current mutable state of a session."""

        try:
            cursor = self._connection.execute(
                """
                UPDATE iam.sessions
                SET
                    csrf_verifier = %s,
                    last_activity_at = %s,
                    idle_expires_at = %s,
                    absolute_expires_at = %s,
                    revoked_at = %s,
                    revocation_reason = %s,
                    authenticated_at = %s,
                    rotation_generation = %s,
                    security_context_version = %s
                WHERE id = %s
                """,
                (
                    session.csrf_verifier,
                    session.last_activity_at,
                    session.idle_expires_at,
                    session.absolute_expires_at,
                    session.revoked_at,
                    session.revocation_reason,
                    session.authenticated_at,
                    session.rotation_generation,
                    session.security_context_version,
                    session.id,
                ),
            )
        except psycopg.IntegrityError as error:
            raise IdentityPersistenceConflict(
                "The session update conflicts with persisted data."
            ) from error
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to update the application session."
            ) from error

        if cursor.rowcount != 1:
            raise IdentityRecordNotFound(
                "The application session does not exist."
            )


class PostgresIdentityUnitOfWork:
    """PostgreSQL transaction boundary for Identity and Access."""

    def __init__(
        self,
        database_url: str,
    ) -> None:
        self._database_url = database_url
        self._connection: Connection[dict[str, Any]] | None = None
        self._committed = False
        self.identities: PostgresIdentityRepository

    def __enter__(self) -> "PostgresIdentityUnitOfWork":
        """Open one PostgreSQL connection and repository."""

        if self._connection is not None:
            raise RuntimeError(
                "The Identity Unit of Work is already active."
            )

        try:
            self._connection = psycopg.connect(
                self._database_url,
                row_factory=dict_row,
            )
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to open the Identity and Access transaction."
            ) from error

        self._committed = False
        self.identities = PostgresIdentityRepository(
            self._connection
        )

        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work and close the connection."""

        connection = self._require_connection()

        try:
            if exception_type is not None or not self._committed:
                connection.rollback()
        finally:
            connection.close()
            self._connection = None
            self._committed = False

    def commit(self) -> None:
        """Commit the current transaction explicitly."""

        connection = self._require_connection()

        try:
            connection.commit()
        except psycopg.Error as error:
            connection.rollback()
            raise IdentityPersistenceError(
                "Unable to commit the Identity and Access transaction."
            ) from error

        self._committed = True

    def rollback(self) -> None:
        """Roll back the current transaction explicitly."""

        connection = self._require_connection()

        try:
            connection.rollback()
        except psycopg.Error as error:
            raise IdentityPersistenceError(
                "Unable to roll back the Identity and Access transaction."
            ) from error

        self._committed = False

    def _require_connection(
        self,
    ) -> Connection[dict[str, Any]]:
        """Return the active connection."""

        if self._connection is None:
            raise RuntimeError(
                "The Identity Unit of Work is not active."
            )

        return self._connection


def _map_user(
    row: dict[str, Any],
) -> InternalUser:
    """Translate one PostgreSQL user row into the domain model."""

    return InternalUser(
        id=row["id"],
        status=UserStatus(row["status"]),
        display_name=row["display_name"],
        primary_email=row["primary_email"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        disabled_at=row["disabled_at"],
        deletion_requested_at=row["deletion_requested_at"],
        version=row["version"],
    )


def _map_external_identity(
    row: dict[str, Any],
) -> ExternalIdentity:
    """Translate one PostgreSQL identity row into the domain model."""

    return ExternalIdentity(
        id=row["id"],
        user_id=row["user_id"],
        provider_type=IdentityProviderType(
            row["provider_type"]
        ),
        issuer=row["issuer"],
        subject=row["subject"],
        created_at=row["created_at"],
        last_authenticated_at=row["last_authenticated_at"],
        disabled_at=row["disabled_at"],
        claims_profile_version=row["claims_profile_version"],
    )


def _map_session(
    row: dict[str, Any],
) -> ApplicationSession:
    """Translate one PostgreSQL session row into the domain model."""

    return ApplicationSession(
        id=row["id"],
        user_id=row["user_id"],
        external_identity_id=row["external_identity_id"],
        authentication_method=AuthenticationMethod(
            row["authentication_method"]
        ),
        session_token_hash=bytes(row["session_token_hash"]),
        csrf_verifier=bytes(row["csrf_verifier"]),
        created_at=row["created_at"],
        last_activity_at=row["last_activity_at"],
        idle_expires_at=row["idle_expires_at"],
        absolute_expires_at=row["absolute_expires_at"],
        revoked_at=row["revoked_at"],
        revocation_reason=row["revocation_reason"],
        authenticated_at=row["authenticated_at"],
        rotation_generation=row["rotation_generation"],
        security_context_version=row["security_context_version"],
    )

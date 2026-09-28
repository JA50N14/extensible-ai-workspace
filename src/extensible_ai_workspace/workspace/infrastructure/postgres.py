"""PostgreSQL persistence for workspaces."""

from types import TracebackType
from typing import Any
from uuid import UUID

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from extensible_ai_workspace.workspace.domain import (
    Workspace,
    WorkspaceStatus,
)


class WorkspacePersistenceError(RuntimeError):
    """Base failure raised by workspace persistence."""


class WorkspacePersistenceConflict(WorkspacePersistenceError):
    """A persisted integrity rule was violated."""


class PostgresWorkspaceRepository:
    """Persist and retrieve workspace domain objects."""

    def __init__(
        self,
        connection: Connection[dict[str, Any]],
    ) -> None:
        self._connection = connection

    def add(
        self,
        workspace: Workspace,
    ) -> None:
        """Persist a new workspace."""

        try:
            self._connection.execute(
                """
                INSERT INTO workspace.workspaces (
                    id,
                    owner_user_id,
                    name,
                    description,
                    status,
                    created_at,
                    updated_at,
                    archived_at,
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
                    %s,
                    %s
                )
                """,
                (
                    workspace.id,
                    workspace.owner_user_id,
                    workspace.name,
                    workspace.description,
                    workspace.status.value,
                    workspace.created_at,
                    workspace.updated_at,
                    workspace.archived_at,
                    workspace.deletion_requested_at,
                    workspace.version,
                ),
            )
        except psycopg.IntegrityError as error:
            raise WorkspacePersistenceConflict(
                "The workspace conflicts with persisted data."
            ) from error
        except psycopg.Error as error:
            raise WorkspacePersistenceError(
                "Unable to persist the workspace."
            ) from error

    def get_for_owner(
        self,
        *,
        workspace_id: UUID,
        owner_user_id: UUID,
    ) -> Workspace | None:
        """Return an active workspace owned by the supplied user."""

        try:
            row = self._connection.execute(
                """
                SELECT
                    id,
                    owner_user_id,
                    name,
                    description,
                    status,
                    created_at,
                    updated_at,
                    archived_at,
                    deletion_requested_at,
                    version
                FROM workspace.workspaces
                WHERE id = %s
                  AND owner_user_id = %s
                  AND status = 'ACTIVE'
                """,
                (
                    workspace_id,
                    owner_user_id,
                ),
            ).fetchone()
        except psycopg.Error as error:
            raise WorkspacePersistenceError(
                "Unable to load the workspace."
            ) from error

        if row is None:
            return None

        return _map_workspace(row)

    def list_for_owner(
        self,
        owner_user_id: UUID,
    ) -> list:
        """Return active workspaces in stable newest-first order."""

        try:
            rows = self._connection.execute(
                """
                SELECT
                    id,
                    owner_user_id,
                    name,
                    description,
                    status,
                    created_at,
                    updated_at,
                    archived_at,
                    deletion_requested_at,
                    version
                FROM workspace.workspaces
                WHERE owner_user_id = %s
                  AND status = 'ACTIVE'
                ORDER BY created_at DESC, id DESC
                """,
                (owner_user_id,),
            ).fetchall()
        except psycopg.Error as error:
            raise WorkspacePersistenceError(
                "Unable to list workspaces."
            ) from error

        return [
            _map_workspace(row)
            for row in rows
        ]


class PostgresWorkspaceUnitOfWork:
    """PostgreSQL transaction boundary for workspace use cases."""

    def __init__(
        self,
        database_url: str,
    ) -> None:
        self._database_url = database_url
        self._connection: Connection[dict[str, Any]] | None = None
        self._committed = False
        self.workspaces: PostgresWorkspaceRepository

    def __enter__(self) -> "PostgresWorkspaceUnitOfWork":
        """Open one PostgreSQL connection and repository."""

        if self._connection is not None:
            raise RuntimeError(
                "The Workspace Unit of Work is already active."
            )

        try:
            self._connection = psycopg.connect(
                self._database_url,
                row_factory=dict_row,
            )
        except psycopg.Error as error:
            raise WorkspacePersistenceError(
                "Unable to open the workspace transaction."
            ) from error

        self._committed = False
        self.workspaces = PostgresWorkspaceRepository(
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
            raise WorkspacePersistenceError(
                "Unable to commit the workspace transaction."
            ) from error

        self._committed = True

    def rollback(self) -> None:
        """Roll back the current transaction explicitly."""

        connection = self._require_connection()

        try:
            connection.rollback()
        except psycopg.Error as error:
            raise WorkspacePersistenceError(
                "Unable to roll back the workspace transaction."
            ) from error

        self._committed = False

    def _require_connection(
        self,
    ) -> Connection[dict[str, Any]]:
        """Return the active PostgreSQL connection."""

        if self._connection is None:
            raise RuntimeError(
                "The Workspace Unit of Work is not active."
            )

        return self._connection


def _map_workspace(
    row: dict[str, Any],
) -> Workspace:
    """Translate one PostgreSQL row into a workspace."""

    return Workspace(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        name=row["name"],
        description=row["description"],
        status=WorkspaceStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
        deletion_requested_at=row["deletion_requested_at"],
        version=row["version"],
    )

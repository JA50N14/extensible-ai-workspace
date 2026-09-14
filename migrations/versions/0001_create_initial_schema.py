"""Create identity, session, and workspace schema.

Revision ID: 0001
Revises:
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial identity, session, and workspace structures."""

    op.execute("CREATE SCHEMA iam")
    op.execute("CREATE SCHEMA workspace")

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "display_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "primary_email",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "disabled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            "status IN "
            "('ACTIVE', 'DISABLED', 'DELETION_REQUESTED', 'PURGED')",
            name="ck_users_status",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_users_version_positive",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_users",
        ),
        schema="iam",
    )

    op.create_table(
        "external_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "provider_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "issuer",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "subject",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "disabled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "claims_profile_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            "provider_type IN ('LOCAL_TRUSTED', 'OIDC')",
            name="ck_external_identities_provider_type",
        ),
        sa.CheckConstraint(
            "claims_profile_version >= 1",
            name="ck_external_identities_claims_profile_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_external_identities_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_external_identities",
        ),
        sa.UniqueConstraint(
            "issuer",
            "subject",
            name="uq_external_identities_issuer_subject",
        ),
        schema="iam",
    )

    op.create_index(
        "ix_external_identities_user_id",
        "external_identities",
        ["user_id"],
        schema="iam",
    )

    op.create_table(
        "sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "external_identity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "authentication_method",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "session_token_hash",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "csrf_verifier",
            sa.LargeBinary(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "idle_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "absolute_expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revocation_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "authenticated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "rotation_generation",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "security_context_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            "authentication_method IN ('LOCAL_TRUSTED', 'OIDC')",
            name="ck_sessions_authentication_method",
        ),
        sa.CheckConstraint(
            "rotation_generation >= 1",
            name="ck_sessions_rotation_generation_positive",
        ),
        sa.CheckConstraint(
            "security_context_version >= 1",
            name="ck_sessions_security_context_version_positive",
        ),
        sa.CheckConstraint(
            "idle_expires_at > created_at",
            name="ck_sessions_idle_expiry_after_creation",
        ),
        sa.CheckConstraint(
            "absolute_expires_at > created_at",
            name="ck_sessions_absolute_expiry_after_creation",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["external_identity_id"],
            ["iam.external_identities.id"],
            name="fk_sessions_external_identity_id_external_identities",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_sessions",
        ),
        sa.UniqueConstraint(
            "session_token_hash",
            name="uq_sessions_session_token_hash",
        ),
        schema="iam",
    )

    op.create_index(
        "ix_sessions_user_id",
        "sessions",
        ["user_id"],
        schema="iam",
    )
    op.create_index(
        "ix_sessions_expiry",
        "sessions",
        ["idle_expires_at", "absolute_expires_at"],
        schema="iam",
    )
    op.create_index(
        "ix_sessions_active_token_hash",
        "sessions",
        ["session_token_hash"],
        unique=True,
        schema="iam",
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deletion_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.CheckConstraint(
            "status IN "
            "('ACTIVE', 'ARCHIVED', 'DELETION_REQUESTED', 'PURGED')",
            name="ck_workspaces_status",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name="ck_workspaces_name_not_blank",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_workspaces_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["iam.users.id"],
            name="fk_workspaces_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_workspaces",
        ),
        schema="workspace",
    )

    op.create_index(
        "ix_workspaces_owner_status_created",
        "workspaces",
        ["owner_user_id", "status", "created_at", "id"],
        schema="workspace",
    )


def downgrade() -> None:
    """Remove the initial identity, session, and workspace structures."""

    op.drop_index(
        "ix_workspaces_owner_status_created",
        table_name="workspaces",
        schema="workspace",
    )
    op.drop_table(
        "workspaces",
        schema="workspace",
    )

    op.drop_index(
        "ix_sessions_active_token_hash",
        table_name="sessions",
        schema="iam",
    )
    op.drop_index(
        "ix_sessions_expiry",
        table_name="sessions",
        schema="iam",
    )
    op.drop_index(
        "ix_sessions_user_id",
        table_name="sessions",
        schema="iam",
    )
    op.drop_table(
        "sessions",
        schema="iam",
    )

    op.drop_index(
        "ix_external_identities_user_id",
        table_name="external_identities",
        schema="iam",
    )
    op.drop_table(
        "external_identities",
        schema="iam",
    )
    op.drop_table(
        "users",
        schema="iam",
    )

    op.execute("DROP SCHEMA workspace")
    op.execute("DROP SCHEMA iam")

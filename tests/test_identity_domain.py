from datetime import UTC, datetime
from uuid import UUID

import pytest

from extensible_ai_workspace.identity.domain import (
    ExternalIdentity,
    IdentityProviderType,
    InternalUser,
    UserStatus,
)

USER_ID = UUID("01990000-0000-7000-8000-000000000001")
IDENTITY_ID = UUID("01990000-0000-7000-8000-000000000002")
CREATED_AT = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def test_active_internal_user_is_valid() -> None:
    user = InternalUser(
        id=USER_ID,
        status=UserStatus.ACTIVE,
        display_name="Local User",
        primary_email=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )

    assert user.is_active is True
    assert user.version == 1


def test_disabled_user_requires_disabled_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="must have disabled_at",
    ):
        InternalUser(
            id=USER_ID,
            status=UserStatus.DISABLED,
            display_name="Local User",
            primary_email=None,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )


def test_internal_user_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValueError,
        match="created_at must be timezone-aware",
    ):
        InternalUser(
            id=USER_ID,
            status=UserStatus.ACTIVE,
            display_name="Local User",
            primary_email=None,
            created_at=datetime(2026, 9, 17, 12, 0),
            updated_at=CREATED_AT,
        )


def test_external_identity_maps_provider_to_internal_user() -> None:
    identity = ExternalIdentity(
        id=IDENTITY_ID,
        user_id=USER_ID,
        provider_type=IdentityProviderType.LOCAL_TRUSTED,
        issuer="extensible-ai-workspace-local",
        subject="local-user",
        created_at=CREATED_AT,
    )

    assert identity.user_id == USER_ID
    assert identity.is_enabled is True
    assert identity.claims_profile_version == 1


def test_external_identity_rejects_blank_subject() -> None:
    with pytest.raises(
        ValueError,
        match="subject cannot be blank",
    ):
        ExternalIdentity(
            id=IDENTITY_ID,
            user_id=USER_ID,
            provider_type=IdentityProviderType.LOCAL_TRUSTED,
            issuer="extensible-ai-workspace-local",
            subject="   ",
            created_at=CREATED_AT,
        )

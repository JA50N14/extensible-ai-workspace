from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
    AuthenticationMethod,
)

SESSION_ID = UUID("01990000-0000-7000-8000-000000000003")
USER_ID = UUID("01990000-0000-7000-8000-000000000001")
IDENTITY_ID = UUID("01990000-0000-7000-8000-000000000002")
CREATED_AT = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


def create_session() -> ApplicationSession:
    return ApplicationSession(
        id=SESSION_ID,
        user_id=USER_ID,
        external_identity_id=IDENTITY_ID,
        authentication_method=AuthenticationMethod.LOCAL_TRUSTED,
        session_token_hash=b"stored-session-token-hash",
        csrf_verifier=b"stored-csrf-verifier",
        created_at=CREATED_AT,
        last_activity_at=CREATED_AT,
        idle_expires_at=CREATED_AT + timedelta(minutes=30),
        absolute_expires_at=CREATED_AT + timedelta(hours=8),
        authenticated_at=CREATED_AT,
    )


def test_session_is_valid_before_expiry() -> None:
    session = create_session()

    assert session.is_valid_at(
        CREATED_AT + timedelta(minutes=10)
    )


@pytest.mark.parametrize(
    "current_time",
    [
        CREATED_AT + timedelta(minutes=30),
        CREATED_AT + timedelta(hours=8),
    ],
)
def test_session_is_invalid_at_expiry_boundary(
    current_time: datetime,
) -> None:
    session = create_session()

    assert session.is_valid_at(current_time) is False


def test_revoked_session_is_invalid() -> None:
    session = create_session()
    revoked_at = CREATED_AT + timedelta(minutes=5)

    revoked_session = session.revoke(
        revoked_at=revoked_at,
        reason="User logged out",
    )

    assert session.is_revoked is False
    assert revoked_session.is_revoked is True
    assert revoked_session.revocation_reason == "User logged out"
    assert revoked_session.is_valid_at(
        CREATED_AT + timedelta(minutes=10)
    ) is False


def test_session_rejects_idle_expiry_after_absolute_expiry() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "idle_expires_at cannot be later than "
            "absolute_expires_at"
        ),
    ):
        ApplicationSession(
            id=SESSION_ID,
            user_id=USER_ID,
            external_identity_id=IDENTITY_ID,
            authentication_method=AuthenticationMethod.LOCAL_TRUSTED,
            session_token_hash=b"stored-session-token-hash",
            csrf_verifier=b"stored-csrf-verifier",
            created_at=CREATED_AT,
            last_activity_at=CREATED_AT,
            idle_expires_at=CREATED_AT + timedelta(hours=9),
            absolute_expires_at=CREATED_AT + timedelta(hours=8),
            authenticated_at=CREATED_AT,
        )


def test_session_rejects_revocation_reason_without_revocation() -> None:
    with pytest.raises(
        ValueError,
        match="active session cannot have a revocation reason",
    ):
        ApplicationSession(
            id=SESSION_ID,
            user_id=USER_ID,
            external_identity_id=IDENTITY_ID,
            authentication_method=AuthenticationMethod.LOCAL_TRUSTED,
            session_token_hash=b"stored-session-token-hash",
            csrf_verifier=b"stored-csrf-verifier",
            created_at=CREATED_AT,
            last_activity_at=CREATED_AT,
            idle_expires_at=CREATED_AT + timedelta(minutes=30),
            absolute_expires_at=CREATED_AT + timedelta(hours=8),
            authenticated_at=CREATED_AT,
            revocation_reason="Unexpected reason",
        )


def test_session_rejects_naive_validity_time() -> None:
    session = create_session()

    with pytest.raises(
        ValueError,
        match="current_time must be timezone-aware",
    ):
        session.is_valid_at(datetime(2026, 9, 17, 12, 10))

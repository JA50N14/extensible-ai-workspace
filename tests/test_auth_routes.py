from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from extensible_ai_workspace.identity.application import (
    AuthenticatedSession,
    EstablishedSession,
    InvalidCsrfToken,
    InvalidSession,
)
from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
    AuthenticationMethod,
    ExternalIdentity,
    IdentityProviderType,
    InternalUser,
    UserStatus,
)
from extensible_ai_workspace.identity.security import (
    CsrfToken,
    SessionCredentials,
    SessionToken,
)
from extensible_ai_workspace.web import create_app

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

USER = InternalUser(
    id=UUID("01990000-0000-7000-8000-000000000301"),
    status=UserStatus.ACTIVE,
    display_name="Local User",
    primary_email=None,
    created_at=NOW,
    updated_at=NOW,
)

IDENTITY = ExternalIdentity(
    id=UUID("01990000-0000-7000-8000-000000000302"),
    user_id=USER.id,
    provider_type=IdentityProviderType.LOCAL_TRUSTED,
    issuer="extensible-ai-workspace-local",
    subject="local-user",
    created_at=NOW,
    last_authenticated_at=NOW,
)

SESSION = ApplicationSession(
    id=UUID("01990000-0000-7000-8000-000000000303"),
    user_id=USER.id,
    external_identity_id=IDENTITY.id,
    authentication_method=AuthenticationMethod.LOCAL_TRUSTED,
    session_token_hash=SessionToken(
        "raw-session-token"
    ).hash(),
    csrf_verifier=CsrfToken(
        "raw-csrf-token"
    ).verifier(),
    created_at=NOW,
    last_activity_at=NOW,
    idle_expires_at=NOW + timedelta(minutes=30),
    absolute_expires_at=NOW + timedelta(hours=8),
    authenticated_at=NOW,
)

CREDENTIALS = SessionCredentials(
    session_token=SessionToken("raw-session-token"),
    csrf_token=CsrfToken("raw-csrf-token"),
)

ESTABLISHED = EstablishedSession(
    user=USER,
    identity=IDENTITY,
    session=SESSION,
    credentials=CREDENTIALS,
)

AUTHENTICATED = AuthenticatedSession(
    user=USER,
    identity=IDENTITY,
    session=SESSION,
)


class FakeSessionService:
    def __init__(self) -> None:
        self.revoked = False

    def establish(self) -> EstablishedSession:
        return ESTABLISHED

    def resolve(
        self,
        session_token: SessionToken,
    ) -> AuthenticatedSession:
        if (
            self.revoked
            or session_token.value != "raw-session-token"
        ):
            raise InvalidSession("Invalid session.")

        return AUTHENTICATED

    def revoke(
        self,
        *,
        session_token: SessionToken,
        csrf_token: CsrfToken,
        reason: str = "User logged out",
    ) -> None:
        if csrf_token.value != "raw-csrf-token":
            raise InvalidCsrfToken("Invalid CSRF token.")

        self.resolve(session_token)
        self.revoked = True


def create_client() -> tuple[TestClient, FakeSessionService]:
    service = FakeSessionService()
    app = create_app(
        session_service_factory=lambda: service,
        public_origin="http://127.0.0.1:8000",
        secure_cookie=False,
    )

    return TestClient(app), service


def test_login_sets_http_only_session_cookie() -> None:
    client, _ = create_client()

    response = client.get("/auth/login")

    assert response.status_code == 200
    assert response.json()["csrf_token"] == "raw-csrf-token"
    assert response.json()["user"]["display_name"] == "Local User"

    set_cookie = response.headers["set-cookie"]

    assert "aiw_session=raw-session-token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Path=/" in set_cookie
    assert "Secure" not in set_cookie
    assert "raw-session-token" not in response.text


def test_session_inspection_returns_safe_metadata() -> None:
    client, _ = create_client()
    client.get("/auth/login")

    response = client.get("/auth/session")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(USER.id)
    assert response.json()["identity"] == {
        "provider_type": "LOCAL_TRUSTED",
        "issuer": "extensible-ai-workspace-local",
    }
    assert "csrf_token" not in response.json()
    assert "session_token" not in response.json()
    assert "csrf_verifier" not in response.text
    assert "raw-session-token" not in response.text
    assert "raw-csrf-token" not in response.text


def test_session_inspection_requires_cookie() -> None:
    client, _ = create_client()

    response = client.get("/auth/session")

    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_INVALID"


def test_logout_requires_matching_origin() -> None:
    client, service = create_client()
    client.get("/auth/login")

    response = client.post(
        "/auth/logout",
        headers={
            "Origin": "http://example.test",
            "X-CSRF-Token": "raw-csrf-token",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert service.revoked is False


def test_logout_rejects_wrong_csrf_token() -> None:
    client, service = create_client()
    client.get("/auth/login")

    response = client.post(
        "/auth/logout",
        headers={
            "Origin": "http://127.0.0.1:8000",
            "X-CSRF-Token": "wrong-csrf-token",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert service.revoked is False


def test_logout_revokes_session_and_clears_cookie() -> None:
    client, service = create_client()
    client.get("/auth/login")

    response = client.post(
        "/auth/logout",
        headers={
            "Origin": "http://127.0.0.1:8000",
            "X-CSRF-Token": "raw-csrf-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}
    assert service.revoked is True

    set_cookie = response.headers["set-cookie"]

    assert "aiw_session=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/" in set_cookie

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from extensible_ai_workspace.identity.application import (
    InactiveIdentity,
    InvalidCsrfToken,
    InvalidSession,
    TrustedLocalIdentity,
    TrustedLocalSessionService,
)
from extensible_ai_workspace.identity.domain import (
    ApplicationSession,
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

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

USER_ID = UUID("01990000-0000-7000-8000-000000000201")
IDENTITY_ID = UUID("01990000-0000-7000-8000-000000000202")
SESSION_ID = UUID("01990000-0000-7000-8000-000000000203")

CREDENTIALS = SessionCredentials(
    session_token=SessionToken("raw-session-token"),
    csrf_token=CsrfToken("raw-csrf-token"),
)


class FakeIdentityRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, InternalUser] = {}
        self.identities: dict[
            tuple[IdentityProviderType, str, str],
            ExternalIdentity,
        ] = {}
        self.sessions: dict[bytes, ApplicationSession] = {}

    def get_user(
        self,
        user_id: UUID,
    ) -> InternalUser | None:
        return self.users.get(user_id)

    def add_user(
        self,
        user: InternalUser,
    ) -> None:
        self.users[user.id] = user

    def get_external_identity(
        self,
        *,
        provider_type: IdentityProviderType,
        issuer: str,
        subject: str,
    ) -> ExternalIdentity | None:
        return self.identities.get(
            (provider_type, issuer, subject)
        )

    def add_external_identity(
        self,
        identity: ExternalIdentity,
    ) -> None:
        self.identities[
            (
                identity.provider_type,
                identity.issuer,
                identity.subject,
            )
        ] = identity

    def add_session(
        self,
        session: ApplicationSession,
    ) -> None:
        self.sessions[session.session_token_hash] = session

    def get_session_by_token_hash(
        self,
        session_token_hash: bytes,
    ) -> ApplicationSession | None:
        return self.sessions.get(session_token_hash)

    def update_session(
        self,
        session: ApplicationSession,
    ) -> None:
        self.sessions[session.session_token_hash] = session


class FakeIdentityUnitOfWork:
    def __init__(
        self,
        repository: FakeIdentityRepository,
    ) -> None:
        self.identities = repository
        self.committed = False

    def __enter__(self) -> "FakeIdentityUnitOfWork":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.committed = False


def create_service(
    repository: FakeIdentityRepository,
    identifiers: list[UUID],
    *,
    current_time: datetime = NOW,
) -> TrustedLocalSessionService:
    identifier_iterator = iter(identifiers)

    return TrustedLocalSessionService(
        unit_of_work_factory=lambda: FakeIdentityUnitOfWork(
            repository
        ),
        trusted_identity=TrustedLocalIdentity(
            issuer="extensible-ai-workspace-local",
            subject="local-user",
            display_name="Local User",
        ),
        clock=lambda: current_time,
        identifier_generator=lambda: next(
            identifier_iterator
        ),
        credential_generator=lambda: CREDENTIALS,
    )


def test_establish_creates_trusted_identity_and_session() -> None:
    repository = FakeIdentityRepository()
    service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )

    result = service.establish()

    assert result.user.id == USER_ID
    assert result.identity.id == IDENTITY_ID
    assert result.session.id == SESSION_ID
    assert result.credentials == CREDENTIALS
    assert (
        result.session.session_token_hash
        == CREDENTIALS.session_token.hash()
    )
    assert (
        result.session.csrf_verifier
        == CREDENTIALS.csrf_token.verifier()
    )
    assert result.session.idle_expires_at == (
        NOW + timedelta(minutes=30)
    )
    assert result.session.absolute_expires_at == (
        NOW + timedelta(hours=8)
    )


def test_establish_reuses_existing_trusted_identity() -> None:
    repository = FakeIdentityRepository()
    user = InternalUser(
        id=USER_ID,
        status=UserStatus.ACTIVE,
        display_name="Local User",
        primary_email=None,
        created_at=NOW,
        updated_at=NOW,
    )
    identity = ExternalIdentity(
        id=IDENTITY_ID,
        user_id=USER_ID,
        provider_type=IdentityProviderType.LOCAL_TRUSTED,
        issuer="extensible-ai-workspace-local",
        subject="local-user",
        created_at=NOW,
        last_authenticated_at=NOW,
    )
    repository.add_user(user)
    repository.add_external_identity(identity)

    service = create_service(
        repository,
        [SESSION_ID],
    )

    result = service.establish()

    assert result.user == user
    assert result.identity == identity
    assert len(repository.users) == 1
    assert len(repository.identities) == 1


def test_resolve_returns_authenticated_session() -> None:
    repository = FakeIdentityRepository()
    service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )
    established = service.establish()

    authenticated = service.resolve(
        CREDENTIALS.session_token
    )

    assert authenticated.user == established.user
    assert authenticated.identity == established.identity
    assert authenticated.session == established.session


def test_resolve_rejects_expired_session() -> None:
    repository = FakeIdentityRepository()
    establishment_service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )
    establishment_service.establish()

    resolution_service = create_service(
        repository,
        [],
        current_time=NOW + timedelta(minutes=30),
    )

    with pytest.raises(InvalidSession):
        resolution_service.resolve(
            CREDENTIALS.session_token
        )


def test_resolve_rejects_inactive_user() -> None:
    repository = FakeIdentityRepository()
    service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )
    established = service.establish()

    repository.users[USER_ID] = InternalUser(
        id=USER_ID,
        status=UserStatus.DISABLED,
        display_name="Local User",
        primary_email=None,
        created_at=NOW,
        updated_at=NOW,
        disabled_at=NOW,
    )

    with pytest.raises(InactiveIdentity):
        service.resolve(
            established.credentials.session_token
        )


def test_validate_csrf_rejects_wrong_token() -> None:
    repository = FakeIdentityRepository()
    service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )
    established = service.establish()
    authenticated = service.resolve(
        established.credentials.session_token
    )

    with pytest.raises(InvalidCsrfToken):
        service.validate_csrf(
            authenticated,
            CsrfToken("wrong-csrf-token"),
        )


def test_revoke_invalidates_server_side_session() -> None:
    repository = FakeIdentityRepository()
    service = create_service(
        repository,
        [USER_ID, IDENTITY_ID, SESSION_ID],
    )
    service.establish()

    service.revoke(
        session_token=CREDENTIALS.session_token,
        csrf_token=CREDENTIALS.csrf_token,
    )

    stored_session = repository.sessions[
        CREDENTIALS.session_token.hash()
    ]

    assert stored_session.is_revoked is True
    assert stored_session.revocation_reason == "User logged out"

    with pytest.raises(InvalidSession):
        service.resolve(
            CREDENTIALS.session_token
        )

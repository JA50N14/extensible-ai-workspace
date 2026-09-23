"""Application use cases for trusted-local sessions."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from extensible_ai_workspace.identity.application.errors import (
    InactiveIdentity,
    InvalidCsrfToken,
    InvalidSession,
)
from extensible_ai_workspace.identity.application.ports import (
    IdentityUnitOfWorkFactory,
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
    generate_session_credentials,
    verify_csrf_token,
)

Clock = Callable[[], datetime]
IdentifierGenerator = Callable[[], UUID]
CredentialGenerator = Callable[[], SessionCredentials]


@dataclass(frozen=True, slots=True, kw_only=True)
class TrustedLocalIdentity:
    """Configured synthetic identity for safe local authentication."""

    issuer: str
    subject: str
    display_name: str

    def __post_init__(self) -> None:
        """Reject incomplete trusted-local identity configuration."""

        _require_text(self.issuer, field_name="issuer")
        _require_text(self.subject, field_name="subject")
        _require_text(
            self.display_name,
            field_name="display_name",
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EstablishedSession:
    """Result returned once when a session is established."""

    user: InternalUser
    identity: ExternalIdentity
    session: ApplicationSession
    credentials: SessionCredentials


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthenticatedSession:
    """Validated authenticated principal and session state."""

    user: InternalUser
    identity: ExternalIdentity
    session: ApplicationSession


class TrustedLocalSessionService:
    """Coordinate trusted-local identity and session use cases."""

    def __init__(
        self,
        *,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        trusted_identity: TrustedLocalIdentity,
        clock: Clock = lambda: datetime.now(UTC),
        identifier_generator: IdentifierGenerator = uuid7,
        credential_generator: CredentialGenerator = (
            generate_session_credentials
        ),
        idle_lifetime: timedelta = timedelta(minutes=30),
        absolute_lifetime: timedelta = timedelta(hours=8),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._trusted_identity = trusted_identity
        self._clock = clock
        self._identifier_generator = identifier_generator
        self._credential_generator = credential_generator
        self._idle_lifetime = idle_lifetime
        self._absolute_lifetime = absolute_lifetime

        if idle_lifetime <= timedelta(0):
            raise ValueError(
                "idle_lifetime must be positive."
            )

        if absolute_lifetime <= timedelta(0):
            raise ValueError(
                "absolute_lifetime must be positive."
            )

        if idle_lifetime > absolute_lifetime:
            raise ValueError(
                "idle_lifetime cannot exceed absolute_lifetime."
            )

    def establish(self) -> EstablishedSession:
        """Resolve or create the trusted identity and establish a session."""

        current_time = self._current_time()
        credentials = self._credential_generator()

        with self._unit_of_work_factory() as unit_of_work:
            identity = unit_of_work.identities.get_external_identity(
                provider_type=IdentityProviderType.LOCAL_TRUSTED,
                issuer=self._trusted_identity.issuer,
                subject=self._trusted_identity.subject,
            )

            if identity is None:
                user, identity = self._create_trusted_identity(
                    created_at=current_time,
                )
                unit_of_work.identities.add_user(user)
                unit_of_work.identities.add_external_identity(
                    identity
                )
            else:
                user = unit_of_work.identities.get_user(
                    identity.user_id
                )

                if user is None:
                    raise InactiveIdentity(
                        "The external identity has no internal user."
                    )

                self._require_active_identity(
                    user=user,
                    identity=identity,
                )

            session = ApplicationSession(
                id=self._identifier_generator(),
                user_id=user.id,
                external_identity_id=identity.id,
                authentication_method=(
                    AuthenticationMethod.LOCAL_TRUSTED
                ),
                session_token_hash=(
                    credentials.session_token.hash()
                ),
                csrf_verifier=credentials.csrf_token.verifier(),
                created_at=current_time,
                last_activity_at=current_time,
                idle_expires_at=(
                    current_time + self._idle_lifetime
                ),
                absolute_expires_at=(
                    current_time + self._absolute_lifetime
                ),
                authenticated_at=current_time,
            )

            unit_of_work.identities.add_session(session)
            unit_of_work.commit()

        return EstablishedSession(
            user=user,
            identity=identity,
            session=session,
            credentials=credentials,
        )

    def resolve(
        self,
        session_token: SessionToken,
    ) -> AuthenticatedSession:
        """Resolve one valid authenticated session."""

        current_time = self._current_time()
        session_token_hash = session_token.hash()

        with self._unit_of_work_factory() as unit_of_work:
            session = (
                unit_of_work.identities.get_session_by_token_hash(
                    session_token_hash
                )
            )

            if session is None or not session.is_valid_at(
                current_time
            ):
                raise InvalidSession(
                    "The application session is invalid."
                )

            if session.external_identity_id is None:
                raise InvalidSession(
                    "The application session has no external identity."
                )

            user = unit_of_work.identities.get_user(
                session.user_id
            )
            identity = (
                unit_of_work.identities.get_external_identity(
                    provider_type=IdentityProviderType.LOCAL_TRUSTED,
                    issuer=self._trusted_identity.issuer,
                    subject=self._trusted_identity.subject,
                )
            )

            if (
                user is None
                or identity is None
                or identity.id != session.external_identity_id
                or identity.user_id != session.user_id
            ):
                raise InvalidSession(
                    "The session identity relationship is invalid."
                )

            self._require_active_identity(
                user=user,
                identity=identity,
            )

        return AuthenticatedSession(
            user=user,
            identity=identity,
            session=session,
        )

    def validate_csrf(
        self,
        authenticated_session: AuthenticatedSession,
        csrf_token: CsrfToken,
    ) -> None:
        """Validate the CSRF token bound to a resolved session."""

        if not verify_csrf_token(
            csrf_token,
            authenticated_session.session.csrf_verifier,
        ):
            raise InvalidCsrfToken(
                "The CSRF token is invalid."
            )

    def revoke(
        self,
        *,
        session_token: SessionToken,
        csrf_token: CsrfToken,
        reason: str = "User logged out",
    ) -> None:
        """Validate and revoke the current server-side session."""

        authenticated_session = self.resolve(session_token)
        self.validate_csrf(
            authenticated_session,
            csrf_token,
        )

        revoked_session = authenticated_session.session.revoke(
            revoked_at=self._current_time(),
            reason=reason,
        )

        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.identities.update_session(
                revoked_session
            )
            unit_of_work.commit()

    def _create_trusted_identity(
        self,
        *,
        created_at: datetime,
    ) -> tuple[InternalUser, ExternalIdentity]:
        """Create the configured synthetic user and identity mapping."""

        user = InternalUser(
            id=self._identifier_generator(),
            status=UserStatus.ACTIVE,
            display_name=self._trusted_identity.display_name,
            primary_email=None,
            created_at=created_at,
            updated_at=created_at,
        )
        identity = ExternalIdentity(
            id=self._identifier_generator(),
            user_id=user.id,
            provider_type=IdentityProviderType.LOCAL_TRUSTED,
            issuer=self._trusted_identity.issuer,
            subject=self._trusted_identity.subject,
            created_at=created_at,
            last_authenticated_at=created_at,
        )

        return user, identity

    def _require_active_identity(
        self,
        *,
        user: InternalUser,
        identity: ExternalIdentity,
    ) -> None:
        """Require an active user and enabled identity mapping."""

        if not user.is_active:
            raise InactiveIdentity(
                "The internal user is not active."
            )

        if not identity.is_enabled:
            raise InactiveIdentity(
                "The external identity is disabled."
            )

    def _current_time(self) -> datetime:
        """Return one timezone-aware application timestamp."""

        current_time = self._clock()

        if (
            current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError(
                "The application clock must return "
                "a timezone-aware timestamp."
            )

        return current_time


def _require_text(
    value: str,
    *,
    field_name: str,
) -> None:
    """Require nonblank textual input."""

    if not value.strip():
        raise ValueError(
            f"{field_name} cannot be blank."
        )

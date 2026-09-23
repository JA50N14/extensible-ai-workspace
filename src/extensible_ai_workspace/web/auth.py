"""FastAPI authentication presentation boundary."""

from collections.abc import Callable

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from extensible_ai_workspace.identity.application import (
    InactiveIdentity,
    InvalidCsrfToken,
    InvalidSession,
    TrustedLocalSessionService,
)
from extensible_ai_workspace.identity.infrastructure import (
    IdentityPersistenceError,
)
from extensible_ai_workspace.identity.security import (
    CsrfToken,
    SessionToken,
)

SESSION_COOKIE_NAME = "aiw_session"
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_MAX_AGE_SECONDS = 8 * 60 * 60

SessionServiceFactory = Callable[[], TrustedLocalSessionService]


def create_auth_router(
    *,
    session_service_factory: SessionServiceFactory,
    public_origin: str,
    secure_cookie: bool,
) -> APIRouter:
    """Create the trusted-local authentication router."""

    router = APIRouter(
        prefix="/auth",
        tags=["authentication"],
    )
    normalized_public_origin = public_origin.rstrip("/")

    @router.get("/login")
    def login() -> JSONResponse:
        """Establish a trusted-local application session."""

        try:
            established = session_service_factory().establish()
        except InactiveIdentity:
            return _authentication_error(
                code="IDENTITY_INACTIVE",
                detail="The configured identity cannot authenticate.",
            )
        except IdentityPersistenceError:
            return _service_unavailable_error()

        response = JSONResponse(
            content={
                "user": {
                    "id": str(established.user.id),
                    "display_name": established.user.display_name,
                    "status": established.user.status.value,
                },
                "session": {
                    "id": str(established.session.id),
                    "authentication_method": (
                        established.session.authentication_method.value
                    ),
                    "created_at": (
                        established.session.created_at.isoformat()
                    ),
                    "idle_expires_at": (
                        established.session.idle_expires_at.isoformat()
                    ),
                    "absolute_expires_at": (
                        established.session.absolute_expires_at.isoformat()
                    ),
                },
                "csrf_token": (
                    established.credentials.csrf_token.value
                ),
            }
        )
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=established.credentials.session_token.value,
            max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
            path=SESSION_COOKIE_PATH,
            secure=secure_cookie,
            httponly=True,
            samesite="strict",
        )

        return response

    @router.get("/session")
    def inspect_session(
        request: Request,
    ) -> JSONResponse:
        """Return safe metadata for the current session."""

        session_token = _read_session_token(request)

        if session_token is None:
            return _invalid_session_error()

        try:
            authenticated = session_service_factory().resolve(
                session_token
            )
        except (InvalidSession, InactiveIdentity):
            return _invalid_session_error()
        except IdentityPersistenceError:
            return _service_unavailable_error()

        return JSONResponse(
            content={
                "user": {
                    "id": str(authenticated.user.id),
                    "display_name": authenticated.user.display_name,
                    "status": authenticated.user.status.value,
                },
                "identity": {
                    "provider_type": (
                        authenticated.identity.provider_type.value
                    ),
                    "issuer": authenticated.identity.issuer,
                },
                "session": {
                    "id": str(authenticated.session.id),
                    "authentication_method": (
                        authenticated.session.authentication_method.value
                    ),
                    "created_at": (
                        authenticated.session.created_at.isoformat()
                    ),
                    "idle_expires_at": (
                        authenticated.session.idle_expires_at.isoformat()
                    ),
                    "absolute_expires_at": (
                        authenticated.session.absolute_expires_at.isoformat()
                    ),
                },
            }
        )

    @router.post("/logout")
    def logout(
        request: Request,
        csrf_token_value: str | None = Header(
            default=None,
            alias="X-CSRF-Token",
        ),
        origin: str | None = Header(
            default=None,
            alias="Origin",
        ),
    ) -> JSONResponse:
        """Revoke the current session and clear its cookie."""

        if origin != normalized_public_origin:
            return _csrf_error(
                detail="The request origin is invalid."
            )

        session_token = _read_session_token(request)

        if session_token is None:
            return _invalid_session_error()

        if csrf_token_value is None:
            return _csrf_error(
                detail="The CSRF token is required."
            )

        try:
            session_service_factory().revoke(
                session_token=session_token,
                csrf_token=CsrfToken(csrf_token_value),
            )
        except InvalidCsrfToken:
            return _csrf_error(
                detail="The CSRF token is invalid."
            )
        except (InvalidSession, InactiveIdentity):
            return _invalid_session_error()
        except IdentityPersistenceError:
            return _service_unavailable_error()
        except ValueError:
            return _csrf_error(
                detail="The CSRF token is invalid."
            )

        response = JSONResponse(
            content={"status": "logged_out"}
        )
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            path=SESSION_COOKIE_PATH,
            secure=secure_cookie,
            httponly=True,
            samesite="strict",
        )

        return response

    return router


def _read_session_token(
    request: Request,
) -> SessionToken | None:
    """Read and validate the opaque session cookie."""

    raw_token = request.cookies.get(SESSION_COOKIE_NAME)

    if raw_token is None:
        return None

    try:
        return SessionToken(raw_token)
    except ValueError:
        return None


def _invalid_session_error() -> JSONResponse:
    """Return the safe invalid-session response."""

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": "SESSION_INVALID",
            "category": "AUTHENTICATION",
            "detail": "A valid application session is required.",
        },
    )


def _authentication_error(
    *,
    code: str,
    detail: str,
) -> JSONResponse:
    """Return a safe authentication failure."""

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "code": code,
            "category": "AUTHENTICATION",
            "detail": detail,
        },
    )


def _csrf_error(
    *,
    detail: str,
) -> JSONResponse:
    """Return a safe CSRF validation failure."""

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "code": "CSRF_INVALID",
            "category": "AUTHORIZATION",
            "detail": detail,
        },
    )


def _service_unavailable_error() -> JSONResponse:
    """Return a safe persistence-dependency failure."""

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "code": "IDENTITY_PERSISTENCE_UNAVAILABLE",
            "category": "DEPENDENCY",
            "detail": (
                "The authentication service is temporarily unavailable."
            ),
        },
    )

"""Application runtime-role dispatch."""

import sys
from functools import partial
from threading import Event

import uvicorn

from extensible_ai_workspace.config import RuntimeRole, Settings
from extensible_ai_workspace.database import check_database_schema
from extensible_ai_workspace.identity.application import (
    TrustedLocalIdentity,
    TrustedLocalSessionService,
)
from extensible_ai_workspace.identity.infrastructure import (
    PostgresIdentityUnitOfWork,
)
from extensible_ai_workspace.web import create_app
from extensible_ai_workspace.web.readiness import (
    create_database_readiness_check,
)


def run_web(settings: Settings) -> None:
    """Start the web runtime."""

    readiness_check = create_database_readiness_check(
        settings.database_url
    )

    trusted_identity = TrustedLocalIdentity(
        issuer=_require_setting(
            settings.local_identity_issuer,
            name="local_identity_issuer",
        ),
        subject=_require_setting(
            settings.local_identity_subject,
            name="local_identity_subject",
        ),
        display_name=_require_setting(
            settings.local_identity_display_name,
            name="local_identity_display_name",
        ),
    )

    unit_of_work_factory = partial(
        PostgresIdentityUnitOfWork,
        settings.database_url,
    )

    session_service_factory = partial(
        TrustedLocalSessionService,
        unit_of_work_factory=unit_of_work_factory,
        trusted_identity=trusted_identity,
    )

    public_origin = str(settings.public_origin).rstrip("/")
    secure_cookie = settings.public_origin.scheme == "https"

    app = create_app(
        readiness_check=readiness_check,
        session_service_factory=session_service_factory,
        public_origin=public_origin,
        secure_cookie=secure_cookie,
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )


def run_worker(settings: Settings) -> None:
    """Start the worker runtime."""

    if not check_database_schema(settings.database_url):
        print(
            "Worker runtime is not ready. "
            "The configured PostgreSQL database or schema is unavailable.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(
        "Extensible AI Workspace worker runtime is ready.",
        flush=True,
    )

    Event().wait()


def run_runtime(settings: Settings) -> None:
    """Start the application in the configured runtime role."""

    match settings.runtime_role:
        case RuntimeRole.WEB:
            run_web(settings)
        case RuntimeRole.WORKER:
            run_worker(settings)


def _require_setting(
    value: str | None,
    *,
    name: str,
) -> str:
    """Narrow one previously validated required setting."""

    if value is None:
        raise RuntimeError(
            f"The validated setting {name} is unavailable."
        )

    return value

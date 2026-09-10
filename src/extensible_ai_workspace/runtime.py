"""Application runtime-role dispatch."""

import uvicorn
import sys
from threading import Event

from extensible_ai_workspace.config import RuntimeRole, Settings
from extensible_ai_workspace.web import create_app
from extensible_ai_workspace.web.readiness import (
    create_database_readiness_check,
)
from extensible_ai_workspace.database import check_database_connection

def run_web(settings: Settings) -> None:
    """Start the web runtime."""

    readiness_check = create_database_readiness_check(
        settings.database_url
    )
    app = create_app(readiness_check=readiness_check)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )

def run_worker(settings: Settings) -> None:
    """Start the worker runtime."""

    if not check_database_connection(settings.database_url):
        print(
            "Worker runtime is not ready. "
            "The configured PostgreSQL database is unavailable.",
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

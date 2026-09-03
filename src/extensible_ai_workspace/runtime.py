"""Application runtime-role dispatch."""

import uvicorn

from extensible_ai_workspace.config import RuntimeRole


def run_web() -> None:
    """Start the web runtime."""

    uvicorn.run(
        "extensible_ai_workspace.web.app:app",
        host="127.0.0.1",
        port=8000,
    )


def run_worker() -> None:
    """Start the worker runtime."""

    print("Extensible AI Workspace worker runtime selected.")


def run_runtime(role: RuntimeRole) -> None:
    """Start the application in the selected runtime role."""

    match role:
        case RuntimeRole.WEB:
            run_web()
        case RuntimeRole.WORKER:
            run_worker()

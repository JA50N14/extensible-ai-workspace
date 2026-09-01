"""Application runtime-role dispatch."""

from extensible_ai_workspace.config import RuntimeRole


def run_web() -> None:
    """Start the web runtime."""

    print("Extensible AI Workspace web runtime selected.")


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

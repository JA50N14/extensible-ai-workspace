"""Extensible AI Workspace."""

import sys

from pydantic import ValidationError

from extensible_ai_workspace.config import Settings
from extensible_ai_workspace.runtime import run_runtime


def main() -> None:
    """Load validated settings and start the selected runtime."""

    try:
        settings = Settings()
    except ValidationError:
        print(
            "Application configuration is invalid. "
            "Check the required AIW_ environment variables.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    run_runtime(settings.runtime_role)

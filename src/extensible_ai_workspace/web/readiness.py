"""Web runtime readiness checks."""

from collections.abc import Callable

ReadinessCheck = Callable[[], bool]


def default_readiness_check() -> bool:
    """Report readiness for the current in-process foundation."""

    return True

from unittest.mock import Mock

import pytest

from extensible_ai_workspace.runtime import run_web


def test_run_web_starts_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    uvicorn_run = Mock()

    monkeypatch.setattr(
        "extensible_ai_workspace.runtime.uvicorn.run",
        uvicorn_run,
    )

    run_web()

    uvicorn_run.assert_called_once_with(
        "extensible_ai_workspace.web.app:app",
        host="127.0.0.1",
        port=8000,
    )

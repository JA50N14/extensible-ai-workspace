from unittest.mock import Mock

import pytest

from extensible_ai_workspace.web.readiness import (
    create_database_readiness_check,
)

TEST_DATABASE_URL = (
    "postgresql://app:development@localhost:5432/"
    "extensible_ai_workspace"
)


def test_database_readiness_check_uses_configured_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_database_connection = Mock(return_value=True)

    monkeypatch.setattr(
        "extensible_ai_workspace.web.readiness.check_database_connection",
        check_database_connection,
    )

    readiness_check = create_database_readiness_check(TEST_DATABASE_URL)

    result = readiness_check()

    assert result is True
    check_database_connection.assert_called_once_with(TEST_DATABASE_URL)

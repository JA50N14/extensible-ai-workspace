import pytest

from extensible_ai_workspace.identity.security import (
    CsrfToken,
    SessionToken,
    generate_session_credentials,
    verify_csrf_token,
    verify_session_token,
)


def test_generated_credentials_are_independent_and_verifiable() -> None:
    credentials = generate_session_credentials()

    assert credentials.session_token.value
    assert credentials.csrf_token.value
    assert (
        credentials.session_token.value
        != credentials.csrf_token.value
    )
    assert verify_session_token(
        credentials.session_token,
        credentials.session_token.hash(),
    )
    assert verify_csrf_token(
        credentials.csrf_token,
        credentials.csrf_token.verifier(),
    )


def test_session_token_rejects_wrong_stored_hash() -> None:
    candidate = SessionToken("candidate-session-token")
    different_token = SessionToken("different-session-token")

    assert (
        verify_session_token(
            candidate,
            different_token.hash(),
        )
        is False
    )


def test_csrf_token_rejects_wrong_stored_verifier() -> None:
    candidate = CsrfToken("candidate-csrf-token")
    different_token = CsrfToken("different-csrf-token")

    assert (
        verify_csrf_token(
            candidate,
            different_token.verifier(),
        )
        is False
    )


@pytest.mark.parametrize(
    "token_factory",
    [
        SessionToken,
        CsrfToken,
    ],
)
def test_tokens_reject_blank_values(
    token_factory: type[SessionToken] | type[CsrfToken],
) -> None:
    with pytest.raises(
        ValueError,
        match="cannot be blank",
    ):
        token_factory("   ")


def test_token_representations_do_not_disclose_raw_values() -> None:
    session_token = SessionToken("raw-session-secret")
    csrf_token = CsrfToken("raw-csrf-secret")

    assert "raw-session-secret" not in repr(session_token)
    assert "raw-csrf-secret" not in repr(csrf_token)

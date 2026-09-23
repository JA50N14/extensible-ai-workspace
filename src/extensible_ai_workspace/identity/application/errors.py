"""Application failures for Identity and Access use cases."""


class AuthenticationError(RuntimeError):
    """Base authentication failure."""


class InvalidSession(AuthenticationError):
    """The supplied session credential is not valid."""


class InactiveIdentity(AuthenticationError):
    """The resolved identity or internal user cannot authenticate."""


class InvalidCsrfToken(AuthenticationError):
    """The supplied CSRF credential is not valid for the session."""

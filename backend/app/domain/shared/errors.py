"""Framework-independent domain errors.

These errors carry a stable machine-readable ``code`` so inbound adapters can
map them to HTTP responses without the domain knowing anything about HTTP.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for every domain error."""

    code: str = "domain_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class ValidationError(DomainError, ValueError):
    """A value violates a domain invariant (maps to HTTP 400/422).

    Also inherits ``ValueError`` so that idiomatic ``except ValueError`` guards
    (and value-object constructors) keep working without importing domain types.
    """

    code = "validation_error"


class NotFoundError(DomainError):
    """A referenced entity does not exist (maps to HTTP 404)."""

    code = "not_found"


class ConflictError(DomainError):
    """The request conflicts with current state (maps to HTTP 409)."""

    code = "conflict"


class AuthorizationError(DomainError):
    """The principal may not perform the requested action (maps to HTTP 403)."""

    code = "forbidden"


class IntegrationError(DomainError):
    """An optional external integration (calendar, mailbox) failed.

    Carries an HTTP-like ``status`` so inbound adapters can map it to a response
    without importing the concrete adapter that raised it.  A default of 502
    reflects that these failures are upstream/unavailable conditions, not client
    mistakes.
    """

    code = "integration_error"

    def __init__(
        self, message: str, *, status: int = 502, code: str | None = None
    ) -> None:
        super().__init__(message, code=code)
        self.status = status

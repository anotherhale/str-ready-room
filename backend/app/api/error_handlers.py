"""FastAPI error handlers.

Map application/domain outcomes to HTTP responses with a consistent, typed
payload.  Route handlers raise domain errors; this module translates them so no
business logic leaks into the transport layer.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..application.ports.persistence import PersistenceError
from ..domain.shared.errors import (
    AuthorizationError,
    ConflictError,
    DomainError,
    IntegrationError,
    NotFoundError,
    ValidationError,
)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    ValidationError: 400,
    NotFoundError: 404,
    ConflictError: 409,
    AuthorizationError: 403,
}


def _payload(code: str, message: str, *, details: object | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
        # IntegrationError carries its own HTTP-like status (502 unavailable,
        # 409 conflict, 404 missing) because an optional upstream integration
        # can fail in ways the generic mapping cannot know about.
        if isinstance(exc, IntegrationError):
            return JSONResponse(status_code=exc.status, content=_payload(exc.code, exc.message))
        status = _STATUS_BY_ERROR.get(type(exc), 400)
        return JSONResponse(status_code=status, content=_payload(exc.code, exc.message))

    @app.exception_handler(PersistenceError)
    async def _persistence_error(_request: Request, exc: PersistenceError) -> JSONResponse:
        return JSONResponse(status_code=500, content=_payload("persistence_error", str(exc)))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload("request_validation_error", "Request validation failed", details=exc.errors()),
        )

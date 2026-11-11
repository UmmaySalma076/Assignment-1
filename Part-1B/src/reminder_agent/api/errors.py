"""Stable HTTP error mapping."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from reminder_agent.contracts.models import ServiceError


class ServiceException(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceException)
    async def service_error_handler(
        _request: Request, exc: ServiceException
    ) -> JSONResponse:
        body = ServiceError(error={"code": exc.code, "message": exc.message})
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        body = ServiceError(
            error={
                "code": "INVALID_REQUEST",
                "message": "Request fields are invalid or exceed configured limits.",
            }
        )
        return JSONResponse(status_code=400, content=body.model_dump())

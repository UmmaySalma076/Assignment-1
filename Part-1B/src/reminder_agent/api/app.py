"""FastAPI application for proposing validated reminder interpretations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi

from reminder_agent.api.errors import ServiceException, install_error_handlers
from reminder_agent.config import Settings
from reminder_agent.contracts.models import InterpretRequest, ModelOutcome, ServiceError
from reminder_agent.services.interpreter import Interpreter
from reminder_agent.services.ollama import OllamaClient


def create_app(
    settings: Settings | None = None, model_client: object | None = None
) -> FastAPI:
    configuration = settings or Settings.from_env()
    ollama = model_client or OllamaClient(configuration)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        close = getattr(ollama, "close", None)
        if close is not None:
            await close()

    application = FastAPI(
        title="Natural-Language Reminder Agent",
        version="1.0.0",
        description="Local-only reminder interpretation; proposals are not persisted or delivered.",
        lifespan=lifespan,
    )
    application.state.settings = configuration
    application.state.model_client = ollama
    install_error_handlers(application)

    @application.post(
        "/v1/reminders/interpret",
        response_model=ModelOutcome,
        responses={400: {"model": ServiceError}, 500: {"model": ServiceError},
                   502: {"model": ServiceError}, 503: {"model": ServiceError},
                   504: {"model": ServiceError}},
    )
    async def interpret(body: InterpretRequest, request: Request) -> ModelOutcome:
        if len(body.text) > configuration.max_request_chars:
            raise ServiceException(
                400,
                "INVALID_REQUEST",
                "text exceeds MAX_REQUEST_CHARS and was not submitted to the model.",
            )
        if body.reference_time is not None and not configuration.allow_evaluation_context:
            raise ServiceException(
                400,
                "INVALID_REQUEST",
                "reference_time is reserved for controlled evaluation.",
            )
        try:
            return await Interpreter(request.app.state.model_client).interpret(
                body,
                clock=body.reference_time,
                timezone_name=body.timezone,
            )
        except ServiceException:
            raise
        except Exception as exc:
            raise ServiceException(
                500, "INTERNAL_ERROR", "An unexpected service error occurred."
            ) from exc

    @application.get("/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @application.get(
        "/health/ready",
        responses={503: {"model": ServiceError}, 504: {"model": ServiceError}},
    )
    async def ready(request: Request) -> dict[str, str]:
        try:
            healthy = await request.app.state.model_client.health()
        except ServiceException:
            raise
        except Exception as exc:
            raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Local Ollama is unavailable.") from exc
        if not healthy:
            raise ServiceException(503, "OLLAMA_UNAVAILABLE", "Local Ollama is unavailable.")
        return {"status": "ready"}

    def stable_openapi() -> dict:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
        )
        for path_item in schema.get("paths", {}).values():
            operation = path_item.get("post")
            if operation:
                operation.get("responses", {}).pop("422", None)
        application.openapi_schema = schema
        return schema

    application.openapi = stable_openapi
    return application


app = create_app()

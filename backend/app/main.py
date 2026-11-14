import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.api.schemas.events import SimulationEventPayload
from app.application.event_history import EventHistory
from app.application.simulation_manager import (
    InvalidCommand,
    SessionAlreadyActive,
    SimulationInternalError,
    SimulationManager,
)
from app.domain.models import InvalidSimulationInput

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as resources:
        application.state.resources = resources
        event_history = EventHistory()
        application.state.event_history = event_history
        manager = SimulationManager(event_history)
        application.state.simulation_manager = manager
        resources.push_async_callback(manager.shutdown)
        application.state.started.set()
        yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="ArchPath Simulation API",
        version="1.0.0",
        description=(
            "API REST para controle de uma simulação single-user mantida em memória. "
            "A primeira versão opera em uma única instância/processo em localhost "
            "ou rede privada confiável. Comandos usam HTTP; eventos usam SSE."
        ),
        servers=[
            {
                "url": "http://localhost:8000",
                "description": "Instância local de desenvolvimento",
            }
        ],
        lifespan=lifespan,
    )
    application.state.started = asyncio.Event()
    application.include_router(api_router, prefix="/api")

    def openapi_schema() -> dict[str, Any]:
        if application.openapi_schema is not None:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            servers=application.servers,
            routes=application.routes,
        )
        schema["components"]["schemas"]["Event"] = SimulationEventPayload.model_json_schema()
        for path_item in schema["paths"].values():
            for operation in path_item.values():
                operation.get("responses", {}).pop("422", None)
        application.openapi_schema = schema
        return schema

    application.openapi = openapi_schema

    @application.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"erro": "Payload ou parâmetros inválidos."},
        )

    @application.exception_handler(InvalidCommand)
    @application.exception_handler(InvalidSimulationInput)
    async def invalid_command_error(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"erro": str(error)})

    @application.exception_handler(SessionAlreadyActive)
    async def active_session_error(_request: Request, error: SessionAlreadyActive) -> JSONResponse:
        return JSONResponse(status_code=409, content={"erro": str(error)})

    @application.exception_handler(SimulationInternalError)
    async def simulation_internal_error(
        _request: Request,
        _error: SimulationInternalError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"erro": "Falha interna irrecuperável durante a simulação."},
        )

    @application.exception_handler(Exception)
    async def unexpected_error(_request: Request, error: Exception) -> JSONResponse:
        logger.error(
            "Erro interno não tratado na API",
            exc_info=(type(error), error, error.__traceback__),
        )
        return JSONResponse(
            status_code=500,
            content={"erro": "Falha interna irrecuperável durante a simulação."},
        )

    @application.get("/healthz", include_in_schema=False)
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()

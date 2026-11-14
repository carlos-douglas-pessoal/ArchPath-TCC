from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.schemas.simulation import (
    ControlResponse,
    ErrorResponse,
    IdleResponse,
    InicioRequest,
    InicioResponse,
    StatusResponse,
)
from app.application.simulation_manager import SimulationManager

router = APIRouter()


@router.post(
    "/iniciar",
    response_model=InicioResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Payload ou entrada inválida."},
        409: {"model": ErrorResponse, "description": "Já existe uma simulação ativa."},
        500: {"model": ErrorResponse, "description": "Falha interna ao iniciar."},
    },
)
async def start_simulation(
    body: InicioRequest,
    request: Request,
) -> InicioResponse:
    manager: SimulationManager = request.app.state.simulation_manager
    session = await manager.start(body.tecla_entrada, body.cenario_memoria)
    return InicioResponse(
        mensagem="Simulação iniciada.",
        estado_fsm="RODANDO",
        sessao_id=session.session_id,
        timestamp_inicio=session.started_at,
    )


@router.post(
    "/pause",
    response_model=ControlResponse,
    response_model_exclude_none=True,
    responses={
        400: {"model": ErrorResponse, "description": "Comando inválido para o estado atual."},
        500: {"model": ErrorResponse, "description": "Falha interna durante a transição."},
    },
)
async def pause_simulation(request: Request) -> ControlResponse:
    manager: SimulationManager = request.app.state.simulation_manager
    return ControlResponse.model_validate(await manager.pause())


@router.post(
    "/resume",
    response_model=ControlResponse,
    response_model_exclude_none=True,
    responses={
        400: {"model": ErrorResponse, "description": "Comando inválido para o estado atual."},
        500: {"model": ErrorResponse, "description": "Falha interna durante a transição."},
    },
)
async def resume_simulation(request: Request) -> ControlResponse:
    manager: SimulationManager = request.app.state.simulation_manager
    return ControlResponse.model_validate(await manager.resume())


@router.post(
    "/step",
    response_model=ControlResponse,
    response_model_exclude_none=True,
    responses={
        400: {"model": ErrorResponse, "description": "Comando inválido para o estado atual."},
        500: {"model": ErrorResponse, "description": "Falha interna durante a transição."},
    },
)
async def step_simulation(request: Request) -> ControlResponse:
    manager: SimulationManager = request.app.state.simulation_manager
    return ControlResponse.model_validate(await manager.step())


@router.get(
    "/status",
    response_model=StatusResponse,
    responses={
        404: {"model": IdleResponse, "description": "Não há simulação ativa."},
    },
)
async def simulation_status(request: Request) -> StatusResponse | JSONResponse:
    manager: SimulationManager = request.app.state.simulation_manager
    current = await manager.status()
    if current is None:
        return JSONResponse(
            status_code=404,
            content=IdleResponse(
                estado_fsm="OCIOSO",
                mensagem="Não há simulação ativa.",
            ).model_dump(mode="json"),
        )
    return StatusResponse.model_validate(current)


@router.get(
    "/eventos",
    response_class=StreamingResponse,
    description=(
        "Fluxo SSE unidirecional. Cada mensagem tem id `<sessao_id>:<sequencia>` e "
        "data JSON conforme Event. O serviço mantém em memória os eventos da sessão "
        "atual/última concluída. Sem Last-Event-ID, reproduz a sessão retida desde o "
        "primeiro evento. Last-Event-ID correspondente à sessão retida continua após "
        "aquele ID; ID inválido ou de sessão anterior reproduz a sessão retida desde "
        "o primeiro evento. Após reinício do processo não há replay persistente. Se "
        "não houver sessão/eventos retidos, a conexão permanece aberta até surgir "
        "evento ou o cliente desconectar."
    ),
    responses={
        200: {
            "description": "Fluxo de eventos SSE.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def events(
    request: Request,
    last_event_id: str | None = Header(
        default=None,
        alias="Last-Event-ID",
        description="ID SSE recebido anteriormente.",
    ),
) -> StreamingResponse:
    async def frames() -> AsyncIterator[str]:
        history = request.app.state.event_history
        async for event in history.subscribe(last_event_id):
            if await request.is_disconnected():
                return
            yield event.frame

    return StreamingResponse(frames(), media_type="text/event-stream")

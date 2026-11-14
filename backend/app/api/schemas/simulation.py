from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, StringConstraints, model_validator

from app.api.schemas.events import SimulationEventPayload


class InicioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tecla_entrada: Annotated[
        StrictStr,
        StringConstraints(min_length=1, max_length=1, pattern=r"^[A-Z0-9 ]$"),
    ]
    cenario_memoria: Literal["normal", "page_fault"] = "normal"


class InicioResponse(BaseModel):
    mensagem: str
    estado_fsm: Literal["RODANDO"]
    sessao_id: UUID
    timestamp_inicio: datetime


class ControlResponse(BaseModel):
    mensagem: str
    estado_fsm: Literal["RODANDO", "PAUSADO", "FINALIZADO"]
    resultado: Literal["sucesso", "erro"] | None = None
    sessao_id: UUID | None = None
    sequencia_evento: int | None = Field(default=None, ge=1)
    evento: SimulationEventPayload | None = None

    @model_validator(mode="after")
    def validate_event_cursor(self) -> "ControlResponse":
        cursor_fields = (self.sessao_id, self.sequencia_evento, self.evento)
        if any(field is not None for field in cursor_fields) and not all(
            field is not None for field in cursor_fields
        ):
            raise ValueError("sessao_id, sequencia_evento e evento devem ser enviados juntos")
        if self.evento is not None and self.evento.sessao_id != self.sessao_id:
            raise ValueError("evento deve pertencer à sessão confirmada")
        if self.evento is not None and self.evento.status_fsm != self.estado_fsm:
            raise ValueError("evento deve refletir o estado confirmado")
        return self


class StatusResponse(BaseModel):
    sessao_id: UUID
    estado_fsm: Literal["RODANDO", "PAUSADO", "AGUARDANDO_STEP"]
    modulo_atual: str
    componente_atual: str
    timestamp_ultima_acao: datetime


class IdleResponse(BaseModel):
    estado_fsm: Literal["OCIOSO"]
    mensagem: str


class ErrorResponse(BaseModel):
    erro: str

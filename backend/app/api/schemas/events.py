from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class SimulationEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    sessao_id: UUID
    status_fsm: Literal["RODANDO", "PAUSADO", "FINALIZADO"]
    modulo_atual: str
    componente_atual: str
    tipo_evento: Literal["TRANSICAO", "ERRO", "FINALIZACAO"]
    acao_executada: str
    estado_do_dado: dict[str, object]

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_include_timezone(cls, timestamp: datetime) -> datetime:
        if timestamp.utcoffset() is None:
            raise ValueError("timestamp deve incluir fuso horário")
        return timestamp

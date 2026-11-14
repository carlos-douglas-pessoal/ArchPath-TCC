import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from app.api.schemas.events import SimulationEventPayload


@dataclass(frozen=True, slots=True)
class StoredEvent:
    session_id: UUID
    sequence: int
    payload_json: str

    @property
    def event_id(self) -> str:
        return f"{self.session_id}:{self.sequence}"

    @property
    def frame(self) -> str:
        return f"id: {self.event_id}\ndata: {self.payload_json}\n\n"


class EventHistory:
    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._events: list[StoredEvent] = []
        self._session_id: UUID | None = None
        self._next_sequence = 1

    async def begin_session(self, session_id: UUID) -> None:
        async with self._condition:
            self._session_id = session_id
            self._events.clear()
            self._next_sequence = 1
            self._condition.notify_all()

    async def publish(self, event: SimulationEventPayload) -> StoredEvent:
        validated_event = SimulationEventPayload.model_validate(event)

        async with self._condition:
            if validated_event.sessao_id != self._session_id:
                self._session_id = validated_event.sessao_id
                self._events.clear()
                self._next_sequence = 1

            stored = StoredEvent(
                session_id=validated_event.sessao_id,
                sequence=self._next_sequence,
                payload_json=validated_event.model_dump_json(),
            )
            self._next_sequence += 1
            self._events.append(stored)
            self._condition.notify_all()
            return stored

    async def subscribe(
        self,
        last_event_id: str | None = None,
    ) -> AsyncIterator[StoredEvent]:
        async with self._condition:
            session_id, sequence = self._resolve_cursor(last_event_id)

        while True:
            async with self._condition:
                if self._session_id is not None and session_id != self._session_id:
                    session_id = self._session_id
                    sequence = 0

                next_event = next(
                    (
                        event
                        for event in self._events
                        if event.session_id == session_id and event.sequence > sequence
                    ),
                    None,
                )
                if next_event is None:
                    await self._condition.wait()
                    continue
                sequence = next_event.sequence

            yield next_event

    def _resolve_cursor(self, last_event_id: str | None) -> tuple[UUID | None, int]:
        if not last_event_id or self._session_id is None:
            return None, 0

        try:
            session_text, sequence_text = last_event_id.rsplit(":", maxsplit=1)
            session_id = UUID(session_text)
            if not sequence_text.isdecimal():
                return None, 0
            sequence = int(sequence_text)
        except (ValueError, AttributeError):
            return None, 0

        if session_id != self._session_id or sequence < 1 or str(sequence) != sequence_text:
            return None, 0
        if not any(event.sequence == sequence for event in self._events):
            return None, 0
        return session_id, sequence

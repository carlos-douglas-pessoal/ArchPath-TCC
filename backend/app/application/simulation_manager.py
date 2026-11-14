import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime

from app.api.schemas.events import SimulationEventPayload
from app.application.event_history import EventHistory
from app.domain.journey import Journey
from app.domain.models import (
    JourneyPhase,
    MemoryScenario,
    SimulationEvent,
    SimulationEventType,
    SimulationSession,
    SimulationState,
)

logger = logging.getLogger(__name__)

BeforeTransition = Callable[[SimulationSession], Awaitable[None]]
TRANSITION_INTERVAL_SECONDS = 1.5


class InvalidCommand(ValueError):
    pass


class SessionAlreadyActive(ValueError):
    pass


class SimulationInternalError(RuntimeError):
    pass


class SimulationManager:
    def __init__(
        self,
        event_history: EventHistory,
        *,
        journey: Journey | None = None,
        before_transition: BeforeTransition | None = None,
    ) -> None:
        self.event_history = event_history
        self.journey = journey or Journey()
        self._before_transition = before_transition
        self._command_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._control_changed = asyncio.Event()
        self._paused = asyncio.Event()
        self._pause_requested = asyncio.Event()
        self._step_completed = asyncio.Event()
        self._active_session: SimulationSession | None = None
        self._motor_task: asyncio.Task[None] | None = None
        self._mode = "STOPPED"
        self._operation_error: Exception | None = None
        self._terminal_result: str | None = None
        self._last_published_event: tuple[int, SimulationEventPayload] | None = None

    async def start(
        self,
        character: str,
        scenario: MemoryScenario | str = MemoryScenario.NORMAL,
    ) -> SimulationSession:
        async with self._command_lock:
            session = SimulationSession.create(character, scenario)
            async with self._state_lock:
                if self._active_session is not None:
                    raise SessionAlreadyActive("Já existe uma simulação ativa.")
                await self.event_history.begin_session(session.session_id)
                self._active_session = session
                self._mode = "RUNNING"
                self._operation_error = None
                self._terminal_result = None
                self._last_published_event = None
                self._control_changed.set()
                self._paused.clear()
                self._pause_requested.clear()
                self._step_completed.clear()
                self._motor_task = asyncio.create_task(
                    self._run_motor(session),
                    name=f"archpath-simulation-{session.session_id}",
                )
            return session

    async def pause(self) -> dict[str, object]:
        async with self._command_lock:
            async with self._state_lock:
                session = self._require_active()
                if session.state is not SimulationState.RUNNING:
                    raise InvalidCommand("A pausa só é aceita durante RODANDO.")
                self._mode = "PAUSED"
                self._operation_error = None
                self._paused.clear()
                self._pause_requested.set()
                self._control_changed.clear()

            await self._paused.wait()
            self._raise_operation_error()
            return await self._command_response("Simulação pausada.", include_event=True)

    async def resume(self) -> dict[str, str]:
        async with self._command_lock:
            async with self._state_lock:
                session = self._require_active()
                if session.state is not SimulationState.PAUSED:
                    raise InvalidCommand("A retomada só é aceita durante PAUSADO.")
                self._mode = "RUNNING"
                session.state = SimulationState.RUNNING
                self._paused.clear()
                self._pause_requested.clear()
                self._operation_error = None
                self._control_changed.set()
            return {"mensagem": "Simulação retomada.", "estado_fsm": "RODANDO"}

    async def step(self) -> dict[str, object]:
        async with self._command_lock:
            async with self._state_lock:
                session = self._require_active()
                if session.state is not SimulationState.PAUSED:
                    raise InvalidCommand("O passo só é aceito durante PAUSADO.")
                self._mode = "STEP"
                session.state = SimulationState.WAITING_STEP
                self._operation_error = None
                self._pause_requested.clear()
                self._step_completed.clear()
                self._control_changed.set()

            await self._step_completed.wait()
            self._raise_operation_error()
            return await self._command_response("Transição concluída.", include_event=True)

    async def status(self) -> dict[str, str] | None:
        async with self._state_lock:
            session = self._active_session
            if session is None:
                return None
            return {
                "sessao_id": str(session.session_id),
                "estado_fsm": session.state.value,
                "modulo_atual": (
                    session.current_phase.value
                    if session.current_phase
                    else JourneyPhase.DATA_BIRTH.value
                ),
                "componente_atual": (
                    session.current_component.value
                    if session.current_component
                    else self.journey.components[0].value
                ),
                "timestamp_ultima_acao": session.last_action_at.isoformat(),
            }

    async def shutdown(self) -> None:
        async with self._state_lock:
            task = self._motor_task
            self._mode = "STOPPED"
            self._active_session = None
            self._pause_requested.set()
            self._control_changed.set()
            self._paused.set()
            self._step_completed.set()

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run_motor(self, session: SimulationSession) -> None:
        try:
            while True:
                async with self._state_lock:
                    if self._active_session is not session:
                        return
                    if self._mode == "PAUSED" and self._last_published_event is not None:
                        session.state = SimulationState.PAUSED
                        self._paused.set()
                        self._control_changed.clear()
                        wait_for_control = True
                    else:
                        wait_for_control = False

                if wait_for_control:
                    await self._control_changed.wait()
                    continue

                await asyncio.sleep(TRANSITION_INTERVAL_SECONDS)
                if self._before_transition is not None:
                    await self._before_transition(session)
                event = self.journey.advance(session)

                async with self._state_lock:
                    if self._active_session is not session:
                        return
                    mode = self._mode
                    if not session.is_terminal and mode in {"PAUSED", "STEP"}:
                        session.state = SimulationState.PAUSED
                        event = replace(event, state=SimulationState.PAUSED)
                    if mode == "STEP" and not session.is_terminal:
                        self._mode = "PAUSED"

                await self._publish_event(event)

                if session.is_terminal:
                    await self._release_session(session)
                    return

                if mode == "STEP":
                    self._step_completed.set()
                elif mode == "PAUSED":
                    self._paused.set()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Erro irrecuperável no motor da sessão %s", session.session_id)
            await self._finish_with_internal_error(session, error)

    async def _finish_with_internal_error(
        self,
        session: SimulationSession,
        error: Exception,
    ) -> None:
        async with self._state_lock:
            if self._active_session is not session:
                return
            session.state = SimulationState.FINISHED
            session.last_action_at = datetime.now(UTC)
            event = SimulationEvent(
                timestamp=session.last_action_at,
                session_id=session.session_id,
                state=SimulationState.FINISHED,
                phase=session.current_phase or JourneyPhase.DATA_BIRTH,
                component=session.current_component or self.journey.components[0],
                action="Erro interno irrecuperável; jornada encerrada",
                event_type=SimulationEventType.ERROR,
                data_snapshot=session.data_snapshot(),
                terminal_result="erro",
            )
            self._operation_error = error
            self._terminal_result = "erro"

        await self._publish_event(event)
        await self._release_session(session)
        self._paused.set()
        self._step_completed.set()

    async def _release_session(self, session: SimulationSession) -> None:
        async with self._state_lock:
            if self._active_session is session:
                if self._operation_error is None:
                    self._terminal_result = "erro" if session.data.get("page_fault") else "sucesso"
                self._active_session = None
                self._mode = "STOPPED"
                self._control_changed.set()
                self._paused.set()
                self._step_completed.set()

    def _event_payload(self, event: SimulationEvent) -> SimulationEventPayload:
        return SimulationEventPayload.model_validate(event.snapshot)

    async def _publish_event(self, event: SimulationEvent) -> None:
        payload = self._event_payload(event)
        stored = await self.event_history.publish(payload)
        self._last_published_event = (stored.sequence, payload)

    def _require_active(self) -> SimulationSession:
        if self._active_session is None:
            raise InvalidCommand("Não há simulação ativa.")
        return self._active_session

    def _raise_operation_error(self) -> None:
        if self._operation_error is not None:
            raise SimulationInternalError("Falha interna durante a transição.") from (
                self._operation_error
            )

    async def _command_response(
        self,
        message: str,
        *,
        include_event: bool = False,
    ) -> dict[str, object]:
        async with self._state_lock:
            event_fields = self._last_event_fields() if include_event else {}
            session = self._active_session
            if session is None:
                error = self._operation_error
                if error is not None:
                    raise SimulationInternalError("Falha interna durante a transição.") from error
                return {
                    "mensagem": (
                        "A simulação foi encerrada por Page Fault."
                        if self._terminal_result == "erro"
                        else "Simulação concluída."
                    ),
                    "estado_fsm": "FINALIZADO",
                    "resultado": self._terminal_result or "sucesso",
                    **event_fields,
                }
            if session.state is SimulationState.FINISHED:
                return {
                    "mensagem": "Simulação concluída.",
                    "estado_fsm": "FINALIZADO",
                    "resultado": "erro",
                    **event_fields,
                }
            return {
                "mensagem": message,
                "estado_fsm": session.state.value,
                **event_fields,
            }

    def _last_event_fields(self) -> dict[str, object]:
        if self._last_published_event is None:
            raise SimulationInternalError("Não há evento publicado para confirmar o controle.")
        sequence, event = self._last_published_event
        return {
            "sessao_id": str(event.sessao_id),
            "sequencia_evento": sequence,
            "evento": event.model_dump(mode="json"),
        }

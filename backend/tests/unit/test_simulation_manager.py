import asyncio

import pytest

from app.application.event_history import EventHistory
from app.application.simulation_manager import (
    InvalidCommand,
    SessionAlreadyActive,
    SimulationInternalError,
    SimulationManager,
)
from app.domain.models import SimulationState


async def pause_at_first_transition(manager: SimulationManager, character="A"):
    transition_started = asyncio.Event()
    release_transition = asyncio.Event()

    async def gate_transition(_session) -> None:
        transition_started.set()
        await release_transition.wait()

    manager._before_transition = gate_transition
    await manager.start(character)
    await transition_started.wait()
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_transition.set()
    return await pause_task


@pytest.mark.asyncio
async def test_simultaneous_starts_allow_only_one_active_session() -> None:
    manager = SimulationManager(EventHistory())
    first, second = await asyncio.gather(
        manager.start("A"),
        manager.start("B"),
        return_exceptions=True,
    )

    accepted = [result for result in (first, second) if not isinstance(result, Exception)]
    rejected = [result for result in (first, second) if isinstance(result, Exception)]

    assert len(accepted) == 1
    assert len(rejected) == 1
    assert isinstance(rejected[0], SessionAlreadyActive)
    assert (await manager.status())["sessao_id"] == str(accepted[0].session_id)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_commands_enforce_fsm_guards_without_mutating_on_rejection() -> None:
    transition_started = asyncio.Event()
    release_transition = asyncio.Event()

    async def gate_transition(_session) -> None:
        transition_started.set()
        await release_transition.wait()

    manager = SimulationManager(EventHistory(), before_transition=gate_transition)

    with pytest.raises(InvalidCommand):
        await manager.pause()
    with pytest.raises(InvalidCommand):
        await manager.resume()
    with pytest.raises(InvalidCommand):
        await manager.step()

    session = await manager.start("A")
    initial_status = await manager.status()
    with pytest.raises(SessionAlreadyActive):
        await manager.start("B")
    assert await manager.status() == initial_status

    await transition_started.wait()
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_transition.set()
    await pause_task
    paused_status = await manager.status()
    with pytest.raises(InvalidCommand):
        await manager.pause()
    assert await manager.status() == paused_status
    await manager.shutdown()
    assert session.state is SimulationState.PAUSED


@pytest.mark.asyncio
async def test_step_executes_exactly_one_transition_and_publishes_before_return() -> None:
    manager = SimulationManager(EventHistory())
    await pause_at_first_transition(manager)
    response = await manager.step()

    assert response["estado_fsm"] == "PAUSADO"
    assert response["sessao_id"] == str((await manager.status())["sessao_id"])
    assert response["sequencia_evento"] == 2
    assert response["evento"]["componente_atual"] == "MicrocontroladorTeclado"
    assert response["evento"]["status_fsm"] == "PAUSADO"
    status = await manager.status()
    assert status["estado_fsm"] == "PAUSADO"
    assert status["componente_atual"] == "MicrocontroladorTeclado"
    replay = manager.event_history.subscribe()
    events = [await anext(replay), await anext(replay)]
    assert events[1].sequence == 2
    assert '"status_fsm":"PAUSADO"' in events[1].payload_json
    assert '"componente_atual":"MicrocontroladorTeclado"' in events[1].payload_json
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_waiting_step_is_transient_and_event_is_published_as_paused() -> None:
    transition_started = asyncio.Event()
    release_transition = asyncio.Event()

    async def gate_transition(_session) -> None:
        transition_started.set()
        await release_transition.wait()

    manager = SimulationManager(EventHistory(), before_transition=gate_transition)
    await manager.start("A")
    await transition_started.wait()
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_transition.set()
    await pause_task

    transition_started.clear()
    release_transition.clear()
    step_task = asyncio.create_task(manager.step())
    await transition_started.wait()

    assert (await manager.status())["estado_fsm"] == "AGUARDANDO_STEP"

    release_transition.set()
    response = await step_task
    assert response["estado_fsm"] == "PAUSADO"
    replay = manager.event_history.subscribe()
    events = [await anext(replay), await anext(replay)]
    assert '"status_fsm":"PAUSADO"' in events[-1].payload_json
    assert "AGUARDANDO_STEP" not in events[-1].payload_json
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_resume_releases_paused_motor_and_pause_stops_after_current_transition() -> None:
    second_transition_started = asyncio.Event()
    release_second_transition = asyncio.Event()

    async def gate_second_transition(session) -> None:
        if session.transition_index == 1:
            second_transition_started.set()
            await release_second_transition.wait()

    manager = SimulationManager(EventHistory(), before_transition=gate_second_transition)
    await manager.start("A")
    await manager.pause()
    resumed = await manager.resume()
    assert resumed["estado_fsm"] == "RODANDO"
    await second_transition_started.wait()
    assert (await manager.status())["estado_fsm"] == "RODANDO"

    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_second_transition.set()
    response = await pause_task

    assert response["estado_fsm"] == "PAUSADO"
    assert response["sequencia_evento"] == 2
    assert response["evento"]["componente_atual"] == "MicrocontroladorTeclado"
    assert response["evento"]["status_fsm"] == "PAUSADO"
    status = await manager.status()
    assert status["componente_atual"] == "MicrocontroladorTeclado"
    await manager.shutdown()


@pytest.mark.asyncio
async def test_pause_waits_for_inflight_transition_and_blocks_the_next() -> None:
    transition_started = asyncio.Event()
    release_transition = asyncio.Event()

    async def gate_transition(_session) -> None:
        transition_started.set()
        await release_transition.wait()

    history = EventHistory()
    manager = SimulationManager(history, before_transition=gate_transition)
    await manager.start("A")
    await transition_started.wait()
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_transition.set()

    response = await pause_task

    assert response["estado_fsm"] == "PAUSADO"
    status = await manager.status()
    assert status["estado_fsm"] == "PAUSADO"
    assert status["componente_atual"] == "MatrizContatos"
    replay = history.subscribe()
    event = await anext(replay)
    assert event.sequence == 1
    assert '"status_fsm":"PAUSADO"' in event.payload_json
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_page_fault_during_pause_returns_terminal_result_and_cleans_session() -> None:
    entered_memory = asyncio.Event()
    release_memory = asyncio.Event()
    history = EventHistory()

    async def gate_memory_transition(session) -> None:
        if session.transition_index == 10:
            entered_memory.set()
            await release_memory.wait()

    manager = SimulationManager(history, before_transition=gate_memory_transition)
    session = await manager.start("A", "page_fault")
    await entered_memory.wait()
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_memory.set()

    response = await pause_task

    assert response["mensagem"] == "A simulação foi encerrada por Page Fault."
    assert response["estado_fsm"] == "FINALIZADO"
    assert response["resultado"] == "erro"
    assert response["sessao_id"] == str(session.session_id)
    assert response["sequencia_evento"] == 11
    assert response["evento"]["status_fsm"] == "FINALIZADO"
    assert response["evento"]["tipo_evento"] == "ERRO"
    assert response["evento"]["sessao_id"] == str(session.session_id)
    assert await manager.status() is None
    replay = history.subscribe()
    terminal = None
    async for event in replay:
        terminal = event
        if '"status_fsm":"FINALIZADO"' in event.payload_json:
            break
    assert terminal is not None
    assert '"tipo_evento":"ERRO"' in terminal.payload_json
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_normal_final_transition_during_pause_returns_success() -> None:
    transition_started = asyncio.Event()
    release_transition = asyncio.Event()
    history = EventHistory()

    async def gate_transition(_session) -> None:
        transition_started.set()
        await release_transition.wait()

    manager = SimulationManager(history, before_transition=gate_transition)
    await manager.start("A")
    await transition_started.wait()
    manager._active_session.transition_index = len(manager.journey.components) - 1
    pause_task = asyncio.create_task(manager.pause())
    await manager._pause_requested.wait()
    release_transition.set()

    response = await pause_task

    assert response["estado_fsm"] == "FINALIZADO"
    assert response["resultado"] == "sucesso"
    assert await manager.status() is None
    replay = history.subscribe()
    event = await anext(replay)
    assert '"tipo_evento":"FINALIZACAO"' in event.payload_json
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_internal_transition_error_publishes_terminal_event_and_cleans_session() -> None:
    history = EventHistory()
    manager = SimulationManager(history)
    await pause_at_first_transition(manager)

    def fail_transition(_session) -> None:
        raise RuntimeError("injected transition failure")

    manager.journey.advance = fail_transition
    with pytest.raises(SimulationInternalError, match="Falha interna"):
        await manager.step()

    assert await manager.status() is None
    replay = history.subscribe()
    events = [await anext(replay), await anext(replay)]
    assert '"tipo_evento":"ERRO"' in events[-1].payload_json
    assert '"status_fsm":"FINALIZADO"' in events[-1].payload_json
    await replay.aclose()

    restarted_session = await manager.start("B")
    assert (await manager.status())["sessao_id"] == str(restarted_session.session_id)
    await manager.shutdown()


@pytest.mark.asyncio
async def test_normal_motor_publishes_terminal_event_then_allows_a_new_session() -> None:
    history = EventHistory()
    manager = SimulationManager(history)
    first_session = await manager.start("A")
    replay = history.subscribe()
    events = [await anext(replay) for _ in manager.journey.components]

    assert events[-1].sequence == len(manager.journey.components)
    assert '"tipo_evento":"FINALIZACAO"' in events[-1].payload_json
    assert '"status_fsm":"FINALIZADO"' in events[-1].payload_json
    assert await manager.status() is None

    second_session = await manager.start("B")
    assert second_session.session_id != first_session.session_id
    assert (await manager.status())["sessao_id"] == str(second_session.session_id)
    await replay.aclose()
    await manager.shutdown()


@pytest.mark.asyncio
async def test_concurrent_steps_are_serialized_and_each_publish_one_transition() -> None:
    manager = SimulationManager(EventHistory())
    await pause_at_first_transition(manager)

    first, second = await asyncio.gather(manager.step(), manager.step())

    assert first["estado_fsm"] == "PAUSADO"
    assert second["estado_fsm"] == "PAUSADO"
    replay = manager.event_history.subscribe()
    events = [await anext(replay) for _ in range(3)]
    assert [event.sequence for event in events] == [1, 2, 3]
    assert '"componente_atual":"MicrocontroladorTeclado"' in events[1].payload_json
    assert '"componente_atual":"CaboConexao"' in events[2].payload_json
    await replay.aclose()
    await manager.shutdown()

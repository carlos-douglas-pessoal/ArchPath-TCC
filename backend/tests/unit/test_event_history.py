import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas.events import SimulationEventPayload
from app.application.event_history import EventHistory


def make_event(session_id=None, *, component="APIC"):
    return SimulationEventPayload(
        timestamp=datetime.now(UTC),
        sessao_id=session_id or uuid4(),
        status_fsm="RODANDO",
        modulo_atual="I/O",
        componente_atual=component,
        tipo_evento="TRANSICAO",
        acao_executada="IRQ levantada",
        estado_do_dado={"irq_levantada": True},
    )


def test_event_payload_rejects_extra_fields_and_invalid_contract_enums() -> None:
    event = make_event().model_dump()

    with pytest.raises(ValidationError):
        SimulationEventPayload.model_validate({**event, "sequencia": 1})

    with pytest.raises(ValidationError):
        SimulationEventPayload.model_validate({**event, "status_fsm": "OCIOSO"})

    with pytest.raises(ValidationError):
        SimulationEventPayload.model_validate(
            {**event, "timestamp": datetime(2026, 10, 17, 12, 0, 0)}
        )


@pytest.mark.asyncio
async def test_history_assigns_per_session_sequence_and_replays_from_start() -> None:
    history = EventHistory()
    session_id = uuid4()
    first = await history.publish(make_event(session_id))
    second = await history.publish(make_event(session_id, component="Chipset"))

    assert (first.sequence, second.sequence) == (1, 2)
    replay = history.subscribe()
    assert await anext(replay) == first
    assert await anext(replay) == second
    await replay.aclose()


@pytest.mark.asyncio
async def test_valid_cursor_replays_only_events_after_that_cursor() -> None:
    history = EventHistory()
    session_id = uuid4()
    await history.publish(make_event(session_id))
    second = await history.publish(make_event(session_id, component="Chipset"))
    await history.publish(make_event(session_id, component="APIC"))

    replay = history.subscribe(f"{session_id}:1")

    assert await anext(replay) == second
    await replay.aclose()


@pytest.mark.parametrize("cursor_kind", ["malformed", "other-session", "unknown-sequence"])
@pytest.mark.asyncio
async def test_invalid_cursor_replays_from_the_first_retained_event(cursor_kind: str) -> None:
    history = EventHistory()
    session_id = uuid4()
    first = await history.publish(make_event(session_id))
    await history.publish(make_event(session_id, component="Chipset"))
    if cursor_kind == "malformed":
        cursor = "not-a-cursor"
    elif cursor_kind == "other-session":
        cursor = f"{uuid4()}:1"
    else:
        cursor = f"{session_id}:99"

    replay = history.subscribe(cursor)

    assert await anext(replay) == first
    await replay.aclose()


@pytest.mark.asyncio
async def test_each_subscriber_receives_its_own_copy_of_events() -> None:
    history = EventHistory()
    first_subscriber = history.subscribe()
    second_subscriber = history.subscribe()
    event = make_event()

    await history.publish(event)

    first, second = await asyncio.gather(
        anext(first_subscriber),
        anext(second_subscriber),
    )
    assert first == second
    await first_subscriber.aclose()
    await second_subscriber.aclose()


@pytest.mark.asyncio
async def test_new_session_replaces_retained_history_and_resets_sequence() -> None:
    history = EventHistory()
    old_session = uuid4()
    await history.publish(make_event(old_session))
    new_event = await history.publish(make_event(uuid4()))

    assert new_event.sequence == 1
    replay = history.subscribe()
    assert await anext(replay) == new_event
    await replay.aclose()


@pytest.mark.asyncio
async def test_accepted_new_session_clears_previous_history_before_first_event() -> None:
    history = EventHistory()
    await history.publish(make_event())
    session_id = uuid4()

    await history.begin_session(session_id)
    first = await history.publish(make_event(session_id))

    assert first.sequence == 1
    replay = history.subscribe()
    assert await anext(replay) == first
    await replay.aclose()


@pytest.mark.asyncio
async def test_new_history_instance_has_no_events_from_previous_process() -> None:
    previous_process = EventHistory()
    await previous_process.publish(make_event())

    restarted_process = EventHistory()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(anext(restarted_process.subscribe()), timeout=0.01)


@pytest.mark.asyncio
async def test_closing_one_subscriber_does_not_consume_or_cancel_events() -> None:
    history = EventHistory()
    disconnected = history.subscribe()
    await disconnected.aclose()
    event = await history.publish(make_event())

    remaining = history.subscribe()
    assert await anext(remaining) == event
    await remaining.aclose()


@pytest.mark.asyncio
async def test_event_arriving_while_subscribers_wait_is_not_lost() -> None:
    history = EventHistory()
    first_subscriber = history.subscribe()
    second_subscriber = history.subscribe()
    first_waiter = asyncio.create_task(anext(first_subscriber))
    second_waiter = asyncio.create_task(anext(second_subscriber))

    event = await history.publish(make_event())

    first, second = await asyncio.gather(first_waiter, second_waiter)
    assert first == event
    assert second == event
    await first_subscriber.aclose()
    await second_subscriber.aclose()

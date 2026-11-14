import asyncio
import json
import socket
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
import uvicorn

from app.api.schemas.events import SimulationEventPayload
from app.main import create_app


@pytest_asyncio.fixture
async def sse_server():
    application = create_app()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = uvicorn.Server(
        uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning")
    )
    task = asyncio.create_task(server.serve())
    try:
        await asyncio.wait_for(application.state.started.wait(), timeout=10)
        yield f"http://127.0.0.1:{port}", application.state.event_history
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


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


async def read_sse_frame(lines: AsyncIterator[str]) -> list[str]:
    frame: list[str] = []
    async for line in lines:
        if line == "":
            return frame
        frame.append(line)
    raise AssertionError("SSE stream closed before a complete frame")


@pytest.mark.asyncio
async def test_sse_route_frames_events_and_replays_after_last_event_id(sse_server) -> None:
    base_url, history = sse_server
    session_id = uuid4()
    await history.publish(make_event(session_id))
    second = await history.publish(make_event(session_id, component="Chipset"))

    async with httpx.AsyncClient(timeout=5) as client:
        async with client.stream(
            "GET",
            f"{base_url}/api/simulacao/eventos",
            headers={"Last-Event-ID": f"{session_id}:1"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            frame = await read_sse_frame(response.aiter_lines())

    assert frame[0] == f"id: {session_id}:2"
    assert frame[1].startswith("data: ")
    payload = json.loads(frame[1][len("data: ") :])
    assert payload["sessao_id"] == str(session_id)
    assert payload["componente_atual"] == "Chipset"
    assert payload["estado_do_dado"] == {"irq_levantada": True}
    assert set(payload) == {
        "timestamp",
        "sessao_id",
        "status_fsm",
        "modulo_atual",
        "componente_atual",
        "tipo_evento",
        "acao_executada",
        "estado_do_dado",
    }
    assert second.sequence == 2


@pytest.mark.asyncio
async def test_sse_route_uses_json_safe_separate_frames(sse_server) -> None:
    base_url, history = sse_server
    first = await history.publish(make_event(component="APIC"))
    second = await history.publish(make_event(first.session_id, component="Chipset"))

    async with httpx.AsyncClient(timeout=5) as client:
        async with client.stream("GET", f"{base_url}/api/simulacao/eventos") as response:
            lines = response.aiter_lines()
            first_frame = await read_sse_frame(lines)
            second_frame = await read_sse_frame(lines)

    assert first_frame[0] == f"id: {first.session_id}:1"
    assert second_frame[0] == f"id: {first.session_id}:2"
    assert second.sequence == 2


@pytest.mark.asyncio
async def test_two_http_subscribers_receive_the_same_published_event(sse_server) -> None:
    base_url, history = sse_server
    async with httpx.AsyncClient(timeout=5) as client:
        async with client.stream("GET", f"{base_url}/api/simulacao/eventos") as first:
            async with client.stream("GET", f"{base_url}/api/simulacao/eventos") as second:
                event = await history.publish(make_event())
                first_frame, second_frame = await asyncio.gather(
                    read_sse_frame(first.aiter_lines()),
                    read_sse_frame(second.aiter_lines()),
                )

    assert first_frame == second_frame
    assert first_frame[0] == f"id: {event.session_id}:1"


@pytest.mark.asyncio
async def test_client_disconnect_does_not_cancel_other_subscribers(sse_server) -> None:
    base_url, history = sse_server

    async with httpx.AsyncClient(timeout=5) as client:
        async with client.stream("GET", f"{base_url}/api/simulacao/eventos"):
            pass

        event = await history.publish(make_event())

        async with client.stream("GET", f"{base_url}/api/simulacao/eventos") as response:
            frame = await read_sse_frame(response.aiter_lines())

    assert frame[0] == f"id: {event.session_id}:1"


@pytest.mark.asyncio
async def test_sse_connection_stays_open_when_history_is_empty(sse_server) -> None:
    base_url, _ = sse_server

    async with httpx.AsyncClient(timeout=5) as client:
        async with client.stream("GET", f"{base_url}/api/simulacao/eventos") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert not response.is_closed

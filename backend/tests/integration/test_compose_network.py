import asyncio
import json
import os
from collections.abc import AsyncIterator

import httpx
import pytest

BASE_URL = os.environ.get("BACKEND_BASE_URL")
RESTART_CHECK = os.environ.get("CHECK_AFTER_BACKEND_RESTART") == "1"


@pytest.fixture
def backend_url() -> str:
    if not BASE_URL:
        pytest.skip("BACKEND_BASE_URL is set by the Compose integration-test service")
    return BASE_URL.rstrip("/") + "/"


async def read_frame(lines: AsyncIterator[str]) -> tuple[str, dict[str, object]]:
    frame: list[str] = []
    async for line in lines:
        if line == "":
            if not frame:
                continue
            break
        frame.append(line)
    else:
        raise AssertionError("SSE stream closed before a complete event")

    event_id = next(line[4:] for line in frame if line.startswith("id: "))
    data = next(line[6:] for line in frame if line.startswith("data: "))
    return event_id, json.loads(data)


async def wait_for_idle(client: httpx.AsyncClient) -> dict[str, object]:
    for _ in range(400):
        response = await client.get("api/simulacao/status")
        if response.status_code == 404:
            return response.json()
        await asyncio.sleep(0.02)
    raise AssertionError("Simulation did not release its session")


@pytest.mark.asyncio
async def test_compose_http_and_sse_complete_normal_journey(backend_url: str) -> None:
    async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
        initial_status = await client.get("api/simulacao/status")
        assert initial_status.status_code == 404

        started = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "A", "cenario_memoria": "normal"},
        )
        assert started.status_code == 200
        session_id = started.json()["sessao_id"]

        async with client.stream("GET", "api/simulacao/eventos") as stream:
            assert stream.status_code == 200
            assert stream.headers["content-type"].startswith("text/event-stream")
            lines = stream.aiter_lines()
            frames = [await read_frame(lines) for _ in range(21)]

        assert [int(event_id.rsplit(":", maxsplit=1)[1]) for event_id, _ in frames] == list(
            range(1, 22)
        )
        assert all(event_id.startswith(f"{session_id}:") for event_id, _ in frames)
        events = [payload for _, payload in frames]
        assert events[0]["componente_atual"] == "MatrizContatos"
        assert events[-1]["componente_atual"] == "ControladorPHY"
        assert events[-1]["status_fsm"] == "FINALIZADO"
        assert events[-1]["tipo_evento"] == "FINALIZACAO"
        assert events[-1]["estado_do_dado"]["transmissao_externa"] is False
        assert await wait_for_idle(client) == {
            "estado_fsm": "OCIOSO",
            "mensagem": "Não há simulação ativa.",
        }


@pytest.mark.asyncio
async def test_compose_http_validates_inputs_and_rejects_second_active_session(
    backend_url: str,
) -> None:
    async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
        for body in (
            {},
            {"tecla_entrada": "a"},
            {"tecla_entrada": "A", "unexpected": True},
        ):
            invalid = await client.post("api/simulacao/iniciar", json=body)
            assert invalid.status_code == 400
            assert set(invalid.json()) == {"erro"}
            assert (await client.get("api/simulacao/status")).status_code == 404

        started = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "E", "cenario_memoria": "normal"},
        )
        assert started.status_code == 200
        session_id = started.json()["sessao_id"]

        conflict = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "F", "cenario_memoria": "page_fault"},
        )
        assert conflict.status_code == 409
        assert set(conflict.json()) == {"erro"}
        active = await client.get("api/simulacao/status")
        assert active.status_code == 200
        assert active.json()["sessao_id"] == session_id
        await wait_for_idle(client)


@pytest.mark.asyncio
async def test_compose_sse_replays_only_events_after_last_event_id(backend_url: str) -> None:
    async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
        started = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "B", "cenario_memoria": "normal"},
        )
        assert started.status_code == 200
        session_id = started.json()["sessao_id"]
        await wait_for_idle(client)

        async with client.stream(
            "GET",
            "api/simulacao/eventos",
            headers={"Last-Event-ID": f"{session_id}:19"},
        ) as stream:
            lines = stream.aiter_lines()
            replay = [await read_frame(lines) for _ in range(2)]

        async with client.stream(
            "GET",
            "api/simulacao/eventos",
            headers={"Last-Event-ID": "anterior:9"},
        ) as stream:
            first_retained_event = await read_frame(stream.aiter_lines())

    assert [event_id for event_id, _ in replay] == [f"{session_id}:20", f"{session_id}:21"]
    assert [payload["tipo_evento"] for _, payload in replay] == ["TRANSICAO", "FINALIZACAO"]
    assert first_retained_event[0] == f"{session_id}:1"


@pytest.mark.asyncio
async def test_compose_sse_supports_multiple_subscribers_and_disconnect_isolation(
    backend_url: str,
) -> None:
    async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
        started = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "C", "cenario_memoria": "normal"},
        )
        assert started.status_code == 200
        session_id = started.json()["sessao_id"]

        async with client.stream("GET", "api/simulacao/eventos") as first:
            async with client.stream("GET", "api/simulacao/eventos") as second:
                first_lines = first.aiter_lines()
                second_lines = second.aiter_lines()
                first_event = await read_frame(first_lines)
                await first.aclose()
                second_event = await read_frame(second_lines)
                remaining = [await read_frame(second_lines) for _ in range(20)]
            await wait_for_idle(client)

    assert first_event == second_event
    assert first_event[0] == f"{session_id}:1"
    assert remaining[-1][0] == f"{session_id}:21"


@pytest.mark.asyncio
async def test_page_fault_http_session_has_no_post_fault_transitions(backend_url: str) -> None:
    async with httpx.AsyncClient(base_url=backend_url, timeout=10) as client:
        started = await client.post(
            "api/simulacao/iniciar",
            json={"tecla_entrada": "D", "cenario_memoria": "page_fault"},
        )
        assert started.status_code == 200
        session_id = started.json()["sessao_id"]
        await wait_for_idle(client)

        async with client.stream("GET", "api/simulacao/eventos") as stream:
            lines = stream.aiter_lines()
            events = [await read_frame(lines) for _ in range(11)]

        fault_event_indexes = [
            index for index, (_, payload) in enumerate(events) if payload["tipo_evento"] == "ERRO"
        ]
        assert fault_event_indexes == [10]
        assert all(event_id.startswith(f"{session_id}:") for event_id, _ in events)
        assert events[-1][1]["componente_atual"] == "GerenciadorMemoria"
        assert events[-1][1]["estado_do_dado"]["buffer_alocado"] is False


@pytest.mark.asyncio
async def test_backend_restart_drops_in_memory_history_when_requested(backend_url: str) -> None:
    if not RESTART_CHECK:
        pytest.skip("Run this assertion after restarting backend in the Compose regression script")

    async with httpx.AsyncClient(base_url=backend_url, timeout=3) as client:
        status = await client.get("api/simulacao/status")
        assert status.status_code == 404
        assert status.json()["estado_fsm"] == "OCIOSO"

        async with client.stream("GET", "api/simulacao/eventos") as stream:
            assert stream.status_code == 200
            iterator = stream.aiter_lines()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(read_frame(iterator), timeout=0.2)

import asyncio
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
import pytest_asyncio
import uvicorn

from app.main import create_app


@pytest_asyncio.fixture
async def api_server():
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
        yield application, f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=10)


@asynccontextmanager
async def client_for(base_url: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        yield client


async def start_held_session(application: Any, client: httpx.AsyncClient, body: dict[str, str]):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def gate_transition(_session) -> None:
        entered.set()
        await release.wait()

    application.state.simulation_manager._before_transition = gate_transition
    response = await client.post("/api/simulacao/iniciar", json=body)
    await asyncio.wait_for(entered.wait(), timeout=2)
    return response, release


@pytest.mark.asyncio
async def test_idle_status_and_openapi_match_rest_contract(api_server) -> None:
    _, base_url = api_server
    async with client_for(base_url) as client:
        idle = await client.get("/api/simulacao/status")
        openapi = (await client.get("/openapi.json")).json()

    assert idle.status_code == 404
    assert idle.json() == {
        "estado_fsm": "OCIOSO",
        "mensagem": "Não há simulação ativa.",
    }
    paths = openapi["paths"]
    assert openapi["info"]["title"] == "ArchPath Simulation API"
    assert openapi["info"]["version"] == "1.0.0"
    assert openapi["servers"][0]["url"] == "http://localhost:8000"
    assert set(paths) >= {
        "/api/simulacao/iniciar",
        "/api/simulacao/pause",
        "/api/simulacao/resume",
        "/api/simulacao/step",
        "/api/simulacao/status",
        "/api/simulacao/eventos",
    }
    assert set(paths["/api/simulacao/iniciar"]["post"]["responses"]) >= {
        "200",
        "400",
        "409",
        "500",
    }
    assert set(paths["/api/simulacao/pause"]["post"]["responses"]) >= {
        "200",
        "400",
        "500",
    }
    for operation in ("resume", "step"):
        assert set(paths[f"/api/simulacao/{operation}"]["post"]["responses"]) >= {
            "200",
            "400",
            "500",
        }
    assert set(paths["/api/simulacao/status"]["get"]["responses"]) >= {"200", "404"}
    control_schema = openapi["components"]["schemas"]["ControlResponse"]
    assert set(control_schema["properties"]) >= {
        "mensagem",
        "estado_fsm",
        "sessao_id",
        "sequencia_evento",
        "evento",
    }
    assert "Last-Event-ID" in str(paths["/api/simulacao/eventos"]["get"])
    event_operation = paths["/api/simulacao/eventos"]["get"]
    assert "reproduz a sessão retida" in event_operation["description"]
    header = next(
        parameter
        for parameter in event_operation["parameters"]
        if parameter["name"] == "Last-Event-ID"
    )
    assert header["description"] == "ID SSE recebido anteriormente."
    request_schema = openapi["components"]["schemas"]["InicioRequest"]
    assert request_schema["additionalProperties"] is False
    assert request_schema["required"] == ["tecla_entrada"]
    assert request_schema["properties"]["tecla_entrada"]["minLength"] == 1
    assert request_schema["properties"]["tecla_entrada"]["maxLength"] == 1
    assert set(request_schema["properties"]["cenario_memoria"]["enum"]) == {
        "normal",
        "page_fault",
    }
    assert not any(
        "422" in operation.get("responses", {})
        for path in paths.values()
        for operation in path.values()
    )
    assert set(openapi["components"]["schemas"]["Event"]["properties"]) == {
        "timestamp",
        "sessao_id",
        "status_fsm",
        "modulo_atual",
        "componente_atual",
        "tipo_evento",
        "acao_executada",
        "estado_do_dado",
    }
    assert (
        "text/event-stream" in paths["/api/simulacao/eventos"]["get"]["responses"]["200"]["content"]
    )


@pytest.mark.asyncio
async def test_start_validates_body_defaults_scenario_and_returns_timestamp(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        invalid_inputs = [
            {},
            {"tecla_entrada": "a"},
            {"tecla_entrada": "AB"},
            {"tecla_entrada": "!"},
            {"tecla_entrada": "A", "extra": True},
            {"tecla_entrada": "A", "cenario_memoria": "unknown"},
        ]
        for body in invalid_inputs:
            response = await client.post("/api/simulacao/iniciar", json=body)
            assert response.status_code == 400
            assert set(response.json()) == {"erro"}

        response, release = await start_held_session(application, client, {"tecla_entrada": "A"})
        status = await client.get("/api/simulacao/status")
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await application.state.simulation_manager._pause_requested.wait()
        release.set()
        await pause_task

    assert response.status_code == 200
    payload = response.json()
    assert payload["mensagem"] == "Simulação iniciada."
    assert payload["estado_fsm"] == "RODANDO"
    assert payload["sessao_id"]
    assert payload["timestamp_inicio"].endswith("+00:00") or payload["timestamp_inicio"].endswith(
        "Z"
    )
    assert status.status_code == 200
    assert status.json()["estado_fsm"] == "RODANDO"


@pytest.mark.asyncio
async def test_active_start_conflict_does_not_replace_session_or_history(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        started, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A", "cenario_memoria": "normal"},
        )
        before = await client.get("/api/simulacao/status")
        conflict = await client.post(
            "/api/simulacao/iniciar",
            json={"tecla_entrada": "B", "cenario_memoria": "page_fault"},
        )
        after = await client.get("/api/simulacao/status")
        release.set()
        await client.post("/api/simulacao/pause")

    assert started.status_code == 200
    assert conflict.status_code == 409
    assert set(conflict.json()) == {"erro"}
    assert before.json() == after.json()


@pytest.mark.asyncio
async def test_start_internal_error_returns_500_without_creating_session(api_server) -> None:
    application, base_url = api_server

    async def fail_start(_character: str, _scenario: str = "normal"):
        raise RuntimeError("internal start failure")

    application.state.simulation_manager.start = fail_start
    async with client_for(base_url) as client:
        response = await client.post("/api/simulacao/iniciar", json={"tecla_entrada": "A"})
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 500
    assert set(response.json()) == {"erro"}
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_pause_resume_step_guards_and_exactly_one_step(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        assert (await client.post("/api/simulacao/pause")).status_code == 400
        assert (await client.post("/api/simulacao/resume")).status_code == 400
        assert (await client.post("/api/simulacao/step")).status_code == 400

        started, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A"},
        )
        assert started.status_code == 200
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await application.state.simulation_manager._pause_requested.wait()
        release.set()
        paused = await pause_task
        repeated_pause = await client.post("/api/simulacao/pause")
        second_entered = asyncio.Event()
        second_release = asyncio.Event()

        async def second_gate(_session) -> None:
            second_entered.set()
            await second_release.wait()

        application.state.simulation_manager._before_transition = second_gate
        resumed = await client.post("/api/simulacao/resume")
        await asyncio.wait_for(second_entered.wait(), timeout=2)
        before_rejected_step = await client.get("/api/simulacao/status")
        invalid_step = await client.post("/api/simulacao/step")
        after_rejected_step = await client.get("/api/simulacao/status")
        second_pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await application.state.simulation_manager._pause_requested.wait()
        second_release.set()
        await second_pause_task
        step_entered = asyncio.Event()
        step_release = asyncio.Event()

        async def step_gate(_session) -> None:
            step_entered.set()
            await step_release.wait()

        application.state.simulation_manager._before_transition = step_gate
        step_task = asyncio.create_task(client.post("/api/simulacao/step"))
        await asyncio.wait_for(step_entered.wait(), timeout=2)
        status = await client.get("/api/simulacao/status")
        step_release.set()
        step = await step_task

    assert paused.status_code == 200
    assert paused.json()["estado_fsm"] == "PAUSADO"
    assert paused.json()["sequencia_evento"] == 1
    assert paused.json()["evento"]["sessao_id"] == paused.json()["sessao_id"]
    assert paused.json()["evento"]["status_fsm"] == "PAUSADO"
    assert repeated_pause.status_code == 400
    assert resumed.status_code == 200
    assert resumed.json()["estado_fsm"] == "RODANDO"
    assert "resultado" not in resumed.json()
    assert invalid_step.status_code == 400
    assert before_rejected_step.json() == after_rejected_step.json()
    assert step.status_code == 200
    assert step.json()["estado_fsm"] == "PAUSADO"
    assert step.json()["sessao_id"] == paused.json()["sessao_id"]
    assert step.json()["sequencia_evento"] == 3
    assert step.json()["evento"]["componente_atual"] == "CaboConexao"
    assert step.json()["evento"]["status_fsm"] == "PAUSADO"
    assert status.json()["estado_fsm"] == "AGUARDANDO_STEP"
    replay = application.state.event_history.subscribe()
    try:
        events = [await anext(replay) for _ in range(3)]
    finally:
        await replay.aclose()
    assert events[-1].sequence == 3
    assert '"status_fsm":"PAUSADO"' in events[-1].payload_json


@pytest.mark.asyncio
async def test_concurrent_http_starts_accept_exactly_one_session(api_server) -> None:
    application, base_url = api_server
    entered = asyncio.Event()
    release = asyncio.Event()

    async def gate_transition(_session) -> None:
        entered.set()
        await release.wait()

    application.state.simulation_manager._before_transition = gate_transition
    async with client_for(base_url) as client:
        first, second = await asyncio.gather(
            client.post("/api/simulacao/iniciar", json={"tecla_entrada": "A"}),
            client.post("/api/simulacao/iniciar", json={"tecla_entrada": "B"}),
        )
        await asyncio.wait_for(entered.wait(), timeout=2)
        accepted = [response for response in (first, second) if response.status_code == 200]
        rejected = [response for response in (first, second) if response.status_code == 409]
        status = await client.get("/api/simulacao/status")
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await application.state.simulation_manager._pause_requested.wait()
        release.set()
        await pause_task

    assert len(accepted) == len(rejected) == 1
    assert set(rejected[0].json()) == {"erro"}
    assert status.json()["sessao_id"] == accepted[0].json()["sessao_id"]


@pytest.mark.asyncio
async def test_page_fault_step_returns_terminal_error_and_cleans_session(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        started, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A", "cenario_memoria": "page_fault"},
        )
        manager = application.state.simulation_manager
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        release.set()
        await pause_task
        manager._active_session.transition_index = 10
        step_task = asyncio.create_task(client.post("/api/simulacao/step"))
        response = await step_task
        status = await client.get("/api/simulacao/status")

    assert started.status_code == 200
    assert response.status_code == 200
    assert response.json()["estado_fsm"] == "FINALIZADO"
    assert response.json()["resultado"] == "erro"
    assert status.status_code == 404
    replay = application.state.event_history.subscribe()
    try:
        terminal = None
        async for terminal in replay:
            if '"status_fsm":"FINALIZADO"' in terminal.payload_json:
                break
    finally:
        await replay.aclose()
    assert terminal is not None
    assert '"tipo_evento":"ERRO"' in terminal.payload_json


@pytest.mark.asyncio
async def test_pause_returns_page_fault_if_transition_finishes_during_wait(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        _, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A", "cenario_memoria": "page_fault"},
        )
        manager = application.state.simulation_manager
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        manager._active_session.transition_index = 10
        release.set()
        response = await pause_task
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 200
    assert response.json()["estado_fsm"] == "FINALIZADO"
    assert response.json()["resultado"] == "erro"
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_pause_returns_500_after_internal_transition_failure(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        _, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A"},
        )
        manager = application.state.simulation_manager

        def fail_transition(_session):
            raise RuntimeError("internal pause failure")

        manager.journey.advance = fail_transition
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        release.set()
        response = await pause_task
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 500
    assert set(response.json()) == {"erro"}
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_pause_returns_terminal_success_if_last_transition_finishes(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        _, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A"},
        )
        manager = application.state.simulation_manager
        manager._active_session.transition_index = len(manager.journey.components) - 1
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        release.set()
        response = await pause_task
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 200
    assert response.json()["estado_fsm"] == "FINALIZADO"
    assert response.json()["resultado"] == "sucesso"
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_step_returns_terminal_success_when_last_transition_finishes(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        _, release = await start_held_session(
            application,
            client,
            {"tecla_entrada": "A"},
        )
        manager = application.state.simulation_manager
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        release.set()
        await pause_task
        manager._active_session.transition_index = len(manager.journey.components) - 1
        response = await client.post("/api/simulacao/step")
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 200
    assert response.json()["estado_fsm"] == "FINALIZADO"
    assert response.json()["resultado"] == "sucesso"
    assert status.status_code == 404


@pytest.mark.asyncio
async def test_step_internal_error_returns_500_after_terminal_cleanup(api_server) -> None:
    application, base_url = api_server
    async with client_for(base_url) as client:
        manager = application.state.simulation_manager
        started, release = await start_held_session(application, client, {"tecla_entrada": "E"})
        assert started.status_code == 200
        pause_task = asyncio.create_task(client.post("/api/simulacao/pause"))
        await manager._pause_requested.wait()
        release.set()
        await pause_task

        def fail(_session):
            raise RuntimeError("internal test failure")

        manager.journey.advance = fail
        response = await client.post("/api/simulacao/step")
        status = await client.get("/api/simulacao/status")

    assert response.status_code == 500
    assert set(response.json()) == {"erro"}
    assert status.status_code == 404
    replay = application.state.event_history.subscribe()
    try:
        events = [await anext(replay) for _ in range(2)]
    finally:
        await replay.aclose()
    assert '"tipo_evento":"ERRO"' in events[-1].payload_json
    async with client_for(base_url) as client:
        restarted = await client.post("/api/simulacao/iniciar", json={"tecla_entrada": "F"})
        assert restarted.status_code == 200

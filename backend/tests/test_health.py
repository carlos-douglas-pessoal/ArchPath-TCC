from contextlib import AsyncExitStack

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def test_application_has_expected_metadata() -> None:
    assert app.title == "ArchPath Simulation API"
    assert app.version == "1.0.0"


@pytest.mark.asyncio
async def test_healthcheck_returns_ok() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_lifespan_closes_registered_resources() -> None:
    closed_resources: list[str] = []

    async with app.router.lifespan_context(app):
        resources = app.state.resources
        assert isinstance(resources, AsyncExitStack)
        resources.callback(closed_resources.append, "closed")

    assert closed_resources == ["closed"]


@pytest.mark.asyncio
async def test_lifespan_owns_one_manager_and_event_history() -> None:
    async with app.router.lifespan_context(app):
        manager = app.state.simulation_manager
        assert manager.event_history is app.state.event_history

    assert await manager.status() is None

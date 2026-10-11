from http import HTTPStatus

import httpx
import pytest

from kamleon.config import Settings
from kamleon.main import create_app


@pytest.fixture
def health_url(url_for):
    return url_for("health")


@pytest.fixture
def ready_url(url_for):
    return url_for("ready")


@pytest.fixture
def get_health(client, health_url):
    async def _():
        return await client.get(health_url)

    return _


@pytest.fixture
def get_ready(client, ready_url):
    async def _():
        return await client.get(ready_url)

    return _


def test_health_url(health_url):
    assert health_url == "/_health"


def test_ready_url(ready_url):
    assert ready_url == "/_health/ready"


async def test_health_endpoint_status_code(get_health):
    response = await get_health()
    assert response.status_code == HTTPStatus.OK


async def test_health_endpoint_data(get_health):
    response = await get_health()
    assert response.json() == {"health": "ok"}


async def test_ready_endpoint_status_code(get_ready):
    response = await get_ready()
    assert response.status_code == HTTPStatus.OK


async def test_ready_endpoint_data(get_ready):
    response = await get_ready()
    assert response.json() == {"health": "ok", "database": "ok"}


async def test_ready_endpoint_reports_unreachable_database():
    # Port 1 refuses connections immediately, so this fails fast.
    app = create_app(Settings(database_url="postgresql+psycopg://x:x@127.0.0.1:1/x"))
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/_health/ready")
            liveness = await client.get("/_health")
    finally:
        await app.state.engine.dispose()

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"health": "unavailable", "database": "unreachable"}
    # Liveness must not depend on the database, or an outage would restart healthy pods.
    assert liveness.status_code == HTTPStatus.OK

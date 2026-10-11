from http import HTTPStatus

from kamleon.config import get_settings
from kamleon.config import Settings
from kamleon.main import create_app


def test_settings_read_the_database_url_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:6543/kamleon")
    assert Settings().database_url == "postgresql+psycopg://u:p@db.example:6543/kamleon"


async def test_create_app_defaults_to_the_environment_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:6543/kamleon")
    get_settings.cache_clear()
    app = create_app()
    try:
        assert app.state.engine.url.host == "db.example"
        assert app.state.engine.url.port == 6543
    finally:
        await app.state.engine.dispose()
        get_settings.cache_clear()


async def test_lifespan_disposes_the_engine_on_shutdown(app):
    async with app.router.lifespan_context(app):
        pass


async def test_openapi_documents_every_endpoint(client):
    response = await client.get("/openapi.json")
    assert response.status_code == HTTPStatus.OK

    operations = {
        (method.upper(), path)
        for path, item in response.json()["paths"].items()
        for method in item
    }
    assert operations == {
        ("POST", "/customers"),
        ("GET", "/customers/{customer_id}"),
        ("DELETE", "/customers/{customer_id}"),
        ("POST", "/customers/{customer_id}/devices"),
        ("GET", "/customers/{customer_id}/devices"),
        ("GET", "/devices/{serial_number}"),
        ("PATCH", "/devices/{serial_number}/status"),
        ("POST", "/devices/{serial_number}/measurements"),
        ("GET", "/devices/{serial_number}/measurements"),
        ("GET", "/_health"),
        ("GET", "/_health/ready"),
    }


async def test_interactive_docs_are_served(client):
    response = await client.get("/docs")
    assert response.status_code == HTTPStatus.OK

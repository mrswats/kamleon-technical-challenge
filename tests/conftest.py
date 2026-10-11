import os
from collections.abc import AsyncIterator
from collections.abc import Iterator
from datetime import datetime
from datetime import UTC
from pathlib import Path

import httpx
import psycopg
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from psycopg import sql
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from kamleon.config import Settings
from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.identity.models import Customer
from kamleon.ingestion.models import Measurement
from kamleon.main import create_app

ROOT = Path(__file__).resolve().parent.parent

# Tests run against a real PostgreSQL (the behaviour under test, row locks and
# ON CONFLICT, is PostgreSQL-specific). This URL only needs to point at a server whose
# user may create databases; each test worker gets its own database on it.
DEFAULT_ADMIN_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"


def conninfo(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def drop_database(admin_url: str, name: str) -> None:
    query = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
    with psycopg.connect(conninfo(admin_url), autocommit=True) as conn:
        conn.execute(query)


@pytest.fixture(scope="session")
def admin_url() -> str:
    return os.environ.get("TEST_DATABASE_URL", DEFAULT_ADMIN_URL)


@pytest.fixture(scope="session")
def database_url(admin_url: str, worker_id: str) -> Iterator[str]:
    """A fresh database per pytest-xdist worker, created by running the real migrations."""
    name = f"kamleon_test_{worker_id}"
    url = make_url(admin_url).set(database=name).render_as_string(hide_password=False)

    drop_database(admin_url, name)
    with psycopg.connect(conninfo(admin_url), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    command.upgrade(make_alembic_config(url), "head")
    yield url
    drop_database(admin_url, name)


def make_alembic_config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.attributes["url"] = url
    return config


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    return make_alembic_config(database_url)


@pytest.fixture
def clean_database(database_url: str) -> None:
    with psycopg.connect(conninfo(database_url), autocommit=True) as conn:
        conn.execute("TRUNCATE measurements, devices, customers RESTART IDENTITY")


@pytest_asyncio.fixture
async def app(database_url: str, clean_database: None) -> AsyncIterator[FastAPI]:
    application = create_app(Settings(database_url=database_url))
    yield application
    await application.state.engine.dispose()


@pytest.fixture
def url_for(app: FastAPI):
    return app.url_path_for


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
async def customer(session: AsyncSession) -> Customer:
    c = Customer(name="Steve", email="steve@example.com")
    session.add(c)
    await session.commit()
    return c


@pytest_asyncio.fixture
async def device(session: AsyncSession, customer: Customer) -> Device:
    d = Device(serial_number="KML-0001", customer_id=customer.id, status=DeviceStatus.ACTIVE)
    session.add(d)
    await session.commit()
    return d


@pytest_asyncio.fixture
async def measurement(session: AsyncSession, device: Device) -> Measurement:
    m = Measurement(
        device_id=device.id,
        type="temperature",
        value=21.5,
        unit="celsius",
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    session.add(m)
    await session.commit()
    return m

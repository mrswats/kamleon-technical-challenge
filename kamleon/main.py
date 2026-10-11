from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from kamleon.config import get_settings
from kamleon.config import Settings
from kamleon.devices.router import router as devices_router
from kamleon.errors import register_exception_handlers
from kamleon.health.router import router as health_router
from kamleon.identity.router import router as identity_router
from kamleon.ingestion.router import router as ingestion_router

DESCRIPTION = """
Manage **customers**, their connected **devices** and the **measurements** those devices
generate.

* A customer can have many devices; a device (unique serial number) belongs to one customer.
* Measurements can only be ingested for existing, `ACTIVE` devices.
* Ingestion is **idempotent**: retrying the same measurement never creates a duplicate.
* Errors raised by business rules look like `{"detail": "...", "code": "..."}`.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory. The database engine lives on `app.state` (no globals), so tests
    and workers can each build an app that points at their own database."""
    settings = settings or get_settings()
    engine = create_async_engine(settings.database_url, echo=settings.echo_sql, pool_pre_ping=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(
        title="Kamleon API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    register_exception_handlers(app)
    app.include_router(identity_router)
    app.include_router(devices_router)
    app.include_router(ingestion_router)
    app.include_router(health_router)
    return app

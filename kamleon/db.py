from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends
from fastapi import Request
from sqlalchemy import DateTime
from sqlalchemy import func
from sqlalchemy import MetaData
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

# Deterministic constraint and index names. They make migrations reproducible and let
# the services recognise *which* constraint was violated (e.g. a duplicate serial number).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Fetch server-generated values (`created_at`, `updated_at`) in the same statement
    # (RETURNING). Required with async sessions, where lazy attribute loads are not allowed.
    __mapper_args__ = {"eager_defaults": True}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request. Services commit explicitly; anything uncommitted (for
    example because an exception was raised) is rolled back when the session closes."""
    async with request.app.state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def violated_constraint(exc: IntegrityError) -> str | None:
    """Name of the database constraint behind an IntegrityError, if the driver reports it."""
    diag = getattr(exc.orig, "diag", None)
    name: str | None = getattr(diag, "constraint_name", None)
    return name

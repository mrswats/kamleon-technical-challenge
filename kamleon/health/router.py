from http import HTTPStatus

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from kamleon.db import SessionDep

router = APIRouter(tags=["health"])


@router.get("/_health", summary="Liveness check")
async def health() -> dict[str, str]:
    """The process is up and serving requests. Does not touch the database."""
    return {"health": "ok"}


@router.get(
    "/_health/ready",
    summary="Readiness check",
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"description": "Database unreachable."}},
)
async def ready(session: SessionDep) -> JSONResponse:
    """The service can reach its database. Use this one for load balancer / orchestrator
    readiness probes, and `/_health` for liveness."""
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content={"health": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(content={"health": "ok", "database": "ok"})

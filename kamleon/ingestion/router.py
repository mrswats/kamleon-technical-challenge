from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter
from fastapi import Query
from fastapi import Response
from pydantic import AwareDatetime

from kamleon.db import SessionDep
from kamleon.errors import ErrorResponse
from kamleon.ingestion import service
from kamleon.ingestion.models import Measurement
from kamleon.ingestion.schemas import MeasurementCreate
from kamleon.ingestion.schemas import MeasurementRead
from kamleon.pagination import Page
from kamleon.pagination import PaginationDep

router = APIRouter(prefix="/devices/{serial_number}/measurements", tags=["measurements"])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=MeasurementRead,
    summary="Ingest a measurement (idempotent)",
    description=(
        "A measurement is identified by (device, type, timestamp). Sending it again, for "
        "example after a network retry, never creates a duplicate: the first request returns "
        "`201`, a retry with the same value and unit returns `200` with the stored "
        "measurement, and a retry with a *different* value or unit returns `409`."
    ),
    responses={
        HTTPStatus.OK: {
            "model": MeasurementRead,
            "description": "The measurement was already stored (idempotent retry).",
        },
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "The device is not ACTIVE, or the measurement contradicts a stored one."
            ),
        },
    },
)
async def ingest_measurement(
    serial_number: str,
    payload: MeasurementCreate,
    session: SessionDep,
    response: Response,
) -> Measurement:
    result = await service.ingest_measurement(session, serial_number, payload)
    if not result.created:
        response.status_code = HTTPStatus.OK
    return result.measurement


@router.get(
    "",
    response_model=Page[MeasurementRead],
    summary="List a device's measurements",
    description=(
        "Newest first. `timestamp_after` and `timestamp_before` are inclusive, must carry a "
        "timezone (use `Z` or an encoded offset such as `%2B02:00`), and filter on when the "
        "measurement was generated."
    ),
    responses={
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.UNPROCESSABLE_CONTENT: {"description": "Invalid query parameters."},
    },
)
async def list_measurements(
    serial_number: str,
    session: SessionDep,
    pagination: PaginationDep,
    type: Annotated[str | None, Query(description="Filter by measurement type.")] = None,
    timestamp_after: Annotated[AwareDatetime | None, Query()] = None,
    timestamp_before: Annotated[AwareDatetime | None, Query()] = None,
) -> Page[MeasurementRead]:
    count, measurements = await service.list_measurements(
        session,
        serial_number,
        measurement_type=type,
        timestamp_after=timestamp_after,
        timestamp_before=timestamp_before,
        pagination=pagination,
    )
    return Page[MeasurementRead](
        count=count,
        limit=pagination.limit,
        offset=pagination.offset,
        results=[MeasurementRead.model_validate(m) for m in measurements],
    )

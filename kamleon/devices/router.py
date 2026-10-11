import uuid
from http import HTTPStatus

from fastapi import APIRouter

from kamleon.db import SessionDep
from kamleon.devices import service
from kamleon.devices.models import Device
from kamleon.devices.schemas import DeviceCreate
from kamleon.devices.schemas import DeviceRead
from kamleon.devices.schemas import DeviceStatusUpdate
from kamleon.errors import ErrorResponse
from kamleon.pagination import Page
from kamleon.pagination import PaginationDep

router = APIRouter(tags=["devices"])


@router.post(
    "/customers/{customer_id}/devices",
    status_code=HTTPStatus.CREATED,
    response_model=DeviceRead,
    summary="Register a device for a customer",
    responses={
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def register_device(
    customer_id: uuid.UUID,
    payload: DeviceCreate,
    session: SessionDep,
) -> Device:
    return await service.register_device(session, customer_id, payload)


@router.get(
    "/customers/{customer_id}/devices",
    response_model=Page[DeviceRead],
    summary="List a customer's devices",
    responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
)
async def list_customer_devices(
    customer_id: uuid.UUID,
    session: SessionDep,
    pagination: PaginationDep,
) -> Page[DeviceRead]:
    count, devices = await service.list_customer_devices(session, customer_id, pagination)
    return Page[DeviceRead](
        count=count,
        limit=pagination.limit,
        offset=pagination.offset,
        results=[DeviceRead.model_validate(device) for device in devices],
    )


@router.get(
    "/devices/{serial_number}",
    response_model=DeviceRead,
    summary="Retrieve a device by serial number",
    responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
)
async def retrieve_device(serial_number: str, session: SessionDep) -> Device:
    return await service.get_device(session, serial_number)


@router.patch(
    "/devices/{serial_number}/status",
    response_model=DeviceRead,
    summary="Activate or deactivate a device",
    responses={
        HTTPStatus.NOT_FOUND: {"model": ErrorResponse},
        HTTPStatus.CONFLICT: {"model": ErrorResponse},
    },
)
async def change_status(
    serial_number: str,
    payload: DeviceStatusUpdate,
    session: SessionDep,
) -> Device:
    return await service.change_status(session, serial_number, payload.status)

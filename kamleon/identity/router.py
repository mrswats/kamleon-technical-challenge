import uuid
from http import HTTPStatus

from fastapi import APIRouter
from fastapi import Response

from kamleon.db import SessionDep
from kamleon.errors import ErrorResponse
from kamleon.identity import service
from kamleon.identity.models import Customer
from kamleon.identity.schemas import CustomerCreate
from kamleon.identity.schemas import CustomerRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=CustomerRead,
    summary="Create a customer",
    responses={HTTPStatus.CONFLICT: {"model": ErrorResponse}},
)
async def create_customer(payload: CustomerCreate, session: SessionDep) -> Customer:
    return await service.create_customer(session, payload)


@router.get(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Retrieve a customer",
    responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
)
async def retrieve_customer(customer_id: uuid.UUID, session: SessionDep) -> Customer:
    return await service.get_customer(session, customer_id)


@router.delete(
    "/{customer_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Delete a customer (anonymise personal data, deactivate devices)",
    description=(
        "GDPR-style erasure: the customer's name and email are anonymised and their devices "
        "are deactivated. Devices and measurements are retained."
    ),
    responses={HTTPStatus.NOT_FOUND: {"model": ErrorResponse}},
)
async def delete_customer(customer_id: uuid.UUID, session: SessionDep) -> Response:
    await service.delete_customer(session, customer_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)

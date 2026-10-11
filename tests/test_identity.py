import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from sqlalchemy import func
from sqlalchemy import select

from kamleon.devices.models import DeviceStatus
from kamleon.identity.service import ANONYMISED_NAME
from kamleon.ingestion.models import Measurement

NEW_CUSTOMER = {"name": "Katie", "email": "katie@example.com"}


@pytest.fixture
def identity_list_url(url_for):
    return url_for("create_customer")


@pytest.fixture
def identity_detail_url(url_for):
    def _(customer_id: str | uuid.UUID) -> str:
        return url_for("retrieve_customer", customer_id=str(customer_id))

    return _


@pytest.fixture
def create_customer(client, identity_list_url):
    async def _(data: dict[str, Any]):
        return await client.post(identity_list_url, json=data)

    return _


@pytest.fixture
def retrieve_customer(client, identity_detail_url):
    async def _(customer_id: str | uuid.UUID):
        return await client.get(identity_detail_url(customer_id))

    return _


@pytest.fixture
def delete_customer(client, identity_detail_url):
    async def _(customer_id: str | uuid.UUID):
        return await client.delete(identity_detail_url(customer_id))

    return _


def test_identity_list_url(identity_list_url):
    assert identity_list_url == "/customers"


def test_identity_detail_url(identity_detail_url):
    assert identity_detail_url("3f2b8c1e-0000-4000-8000-000000000001") == (
        "/customers/3f2b8c1e-0000-4000-8000-000000000001"
    )


async def test_identity_retrieve_customer_status_code(retrieve_customer, customer):
    response = await retrieve_customer(customer.id)
    assert response.status_code == HTTPStatus.OK


async def test_identity_retrieve_customer_data(retrieve_customer, customer):
    response = await retrieve_customer(customer.id)
    assert response.json() == {
        "id": str(customer.id),
        "name": "Steve",
        "email": "steve@example.com",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }
    datetime.fromisoformat(response.json()["created_at"])  # a real timestamp, not just "any"


async def test_identity_retrieve_unknown_customer_status_code(retrieve_customer):
    response = await retrieve_customer(uuid.uuid4())
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Customer not found", "code": "customer_not_found"}


async def test_identity_retrieve_malformed_id_status_code(retrieve_customer):
    response = await retrieve_customer("not-a-uuid")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


async def test_identity_create_customer_status_code(create_customer):
    response = await create_customer(NEW_CUSTOMER)
    assert response.status_code == HTTPStatus.CREATED


async def test_identity_create_customer_data(create_customer):
    response = await create_customer(NEW_CUSTOMER)
    body = response.json()
    assert body == {
        "id": mock.ANY,
        "name": "Katie",
        "email": "katie@example.com",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }
    uuid.UUID(body["id"])


async def test_identity_create_customer_can_be_retrieved(create_customer, retrieve_customer):
    created = (await create_customer(NEW_CUSTOMER)).json()
    response = await retrieve_customer(created["id"])
    assert response.json() == created


async def test_identity_create_customer_normalises_name_and_email(create_customer):
    response = await create_customer({"name": "  Katie  ", "email": "Katie@Example.COM"})
    assert response.json()["name"] == "Katie"
    assert response.json()["email"] == "katie@example.com"


async def test_identity_create_duplicate_email_status_code(create_customer, customer):
    response = await create_customer({"name": "Other", "email": "steve@example.com"})
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {
        "detail": "A customer with this email already exists",
        "code": "duplicate_email",
    }


async def test_identity_create_duplicate_email_is_case_insensitive(create_customer, customer):
    response = await create_customer({"name": "Other", "email": "STEVE@example.com"})
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"name": "Katie"},
        {"email": "katie@example.com"},
        {"name": "", "email": "katie@example.com"},
        {"name": "x" * 151, "email": "katie@example.com"},
        {"name": "Katie", "email": "not-an-email"},
        # Credentials are not part of this API: unknown fields are rejected, not ignored.
        {**NEW_CUSTOMER, "password": "hunter2"},
    ],
)
async def test_identity_create_invalid_payload_status_code(create_customer, data):
    response = await create_customer(data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


async def test_identity_delete_customer_status_code(delete_customer, customer):
    response = await delete_customer(customer.id)
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""


async def test_identity_deleted_customer_is_not_retrievable(
    delete_customer, retrieve_customer, customer
):
    await delete_customer(customer.id)
    response = await retrieve_customer(customer.id)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_identity_delete_customer_twice_status_code(delete_customer, customer):
    await delete_customer(customer.id)
    response = await delete_customer(customer.id)
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_identity_delete_unknown_customer_status_code(delete_customer):
    response = await delete_customer(uuid.uuid4())
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_identity_delete_customer_anonymises_personal_data(
    delete_customer, session, customer
):
    await delete_customer(customer.id)

    await session.refresh(customer)
    assert customer.name == ANONYMISED_NAME
    assert customer.email == f"deleted-{customer.id}@anonymised.invalid"
    assert customer.deleted_at is not None


async def test_identity_delete_customer_deactivates_devices_but_keeps_data(
    delete_customer, session, customer, device, measurement
):
    await delete_customer(customer.id)

    await session.refresh(device)
    assert device.status is DeviceStatus.INACTIVE
    assert await session.scalar(select(func.count()).select_from(Measurement)) == 1


async def test_identity_email_can_be_reused_after_deletion(
    delete_customer, create_customer, customer
):
    await delete_customer(customer.id)
    response = await create_customer({"name": "Steve again", "email": "steve@example.com"})
    assert response.status_code == HTTPStatus.CREATED

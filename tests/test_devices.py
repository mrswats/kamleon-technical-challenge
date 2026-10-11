import asyncio
import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from sqlalchemy import func
from sqlalchemy import select

from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus


@pytest.fixture
def device_list_url(url_for):
    def _(customer_id: str | uuid.UUID) -> str:
        return url_for("register_device", customer_id=str(customer_id))

    return _


@pytest.fixture
def device_detail_url(url_for):
    def _(serial_number: str) -> str:
        return url_for("retrieve_device", serial_number=serial_number)

    return _


@pytest.fixture
def device_detail_status_change_url(url_for):
    def _(serial_number: str) -> str:
        return url_for("change_status", serial_number=serial_number)

    return _


@pytest.fixture
def create_device(client, device_list_url):
    async def _(customer_id: str | uuid.UUID, data: dict[str, Any]):
        return await client.post(device_list_url(customer_id), json=data)

    return _


@pytest.fixture
def list_devices(client, device_list_url):
    async def _(customer_id: str | uuid.UUID, queries: dict[str, Any] | None = None):
        return await client.get(device_list_url(customer_id), params=queries or {})

    return _


@pytest.fixture
def retrieve_device(client, device_detail_url):
    async def _(serial_number: str):
        return await client.get(device_detail_url(serial_number))

    return _


@pytest.fixture
def update_status_device(client, device_detail_status_change_url):
    async def _(serial_number: str, status: str, **extra: Any):
        return await client.patch(
            device_detail_status_change_url(serial_number),
            json={"status": status, **extra},
        )

    return _


def test_device_list_url(device_list_url):
    customer_id = "3f2b8c1e-0000-4000-8000-000000000001"
    assert device_list_url(customer_id) == f"/customers/{customer_id}/devices"


def test_device_detail_url(device_detail_url):
    assert device_detail_url("KML-3141592") == "/devices/KML-3141592"


def test_device_status_change_url(device_detail_status_change_url):
    assert device_detail_status_change_url("KML-3141592") == "/devices/KML-3141592/status"


async def test_retrieve_device_status_code(retrieve_device, device):
    response = await retrieve_device(device.serial_number)
    assert response.status_code == HTTPStatus.OK


async def test_retrieve_device_non_existing_status_code(retrieve_device):
    response = await retrieve_device("KML-3141592")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Device not found", "code": "device_not_found"}


async def test_retrieve_device_data(retrieve_device, device, customer):
    response = await retrieve_device(device.serial_number)
    assert response.json() == {
        "id": str(device.id),
        "serial_number": "KML-0001",
        "customer_id": str(customer.id),
        "status": "ACTIVE",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }


async def test_create_device_status_code(create_device, customer):
    response = await create_device(customer.id, {"serial_number": "KML-0002"})
    assert response.status_code == HTTPStatus.CREATED


async def test_create_device_data(create_device, customer):
    response = await create_device(customer.id, {"serial_number": "KML-0002"})
    body = response.json()
    assert body == {
        "id": mock.ANY,
        "serial_number": "KML-0002",
        "customer_id": str(customer.id),
        "status": "INACTIVE",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }
    uuid.UUID(body["id"])


async def test_create_device_with_explicit_status(create_device, customer):
    response = await create_device(customer.id, {"serial_number": "KML-0002", "status": "ACTIVE"})
    assert response.json()["status"] == "ACTIVE"


async def test_create_device_can_be_retrieved(create_device, retrieve_device, customer):
    created = (await create_device(customer.id, {"serial_number": "KML-0002"})).json()
    response = await retrieve_device("KML-0002")
    assert response.json() == created


async def test_create_device_unknown_customer_status_code(create_device):
    response = await create_device(uuid.uuid4(), {"serial_number": "KML-0002"})
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["code"] == "customer_not_found"


async def test_create_device_for_deleted_customer_status_code(client, create_device, customer):
    await client.delete(f"/customers/{customer.id}")
    response = await create_device(customer.id, {"serial_number": "KML-0002"})
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_create_device_duplicate_serial_number_status_code(create_device, customer, device):
    response = await create_device(customer.id, {"serial_number": device.serial_number})
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {
        "detail": "A device with this serial number already exists",
        "code": "duplicate_serial_number",
    }


async def test_create_device_duplicate_serial_number_for_another_customer(
    client, create_device, device
):
    other = (await client.post("/customers", json={"name": "B", "email": "b@example.com"})).json()
    response = await create_device(other["id"], {"serial_number": device.serial_number})
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"serial_number": ""},
        {"serial_number": "has space"},
        {"serial_number": "snowman-☃"},
        {"serial_number": "x" * 65},
        {"serial_number": "KML-0002", "status": "BROKEN"},
        # The owner comes from the URL; it cannot also be supplied (or contradicted) in the body.
        {"serial_number": "KML-0002", "customer_id": str(uuid.uuid4())},
    ],
)
async def test_create_device_invalid_payload_status_code(create_device, customer, data):
    response = await create_device(customer.id, data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


async def test_create_device_concurrent_duplicate_serial_numbers(create_device, customer, session):
    """The UNIQUE constraint decides: of N simultaneous registrations exactly one wins."""
    responses = await asyncio.gather(
        *(create_device(customer.id, {"serial_number": "KML-RACE"}) for _ in range(10))
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [HTTPStatus.CREATED] + [HTTPStatus.CONFLICT] * 9
    count = await session.scalar(select(func.count()).select_from(Device))
    assert count == 1


async def test_list_customer_devices_data(list_devices, customer, device):
    response = await list_devices(customer.id)
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "count": 1,
        "limit": 10,
        "offset": 0,
        "results": [
            {
                "id": str(device.id),
                "serial_number": "KML-0001",
                "customer_id": str(customer.id),
                "status": "ACTIVE",
                "created_at": mock.ANY,
                "updated_at": mock.ANY,
            }
        ],
    }


async def test_list_customer_devices_empty(list_devices, customer):
    response = await list_devices(customer.id)
    assert response.json() == {"count": 0, "limit": 10, "offset": 0, "results": []}


async def test_list_customer_devices_pagination(list_devices, create_device, customer):
    for number in range(3):
        await create_device(customer.id, {"serial_number": f"KML-PAGE-{number}"})

    first = (await list_devices(customer.id, {"limit": 2})).json()
    second = (await list_devices(customer.id, {"limit": 2, "offset": 2})).json()

    assert first["count"] == second["count"] == 3
    assert [d["serial_number"] for d in first["results"]] == ["KML-PAGE-0", "KML-PAGE-1"]
    assert [d["serial_number"] for d in second["results"]] == ["KML-PAGE-2"]


async def test_list_customer_devices_only_returns_own_devices(
    client, list_devices, create_device, customer, device
):
    other = (await client.post("/customers", json={"name": "B", "email": "b@example.com"})).json()
    await create_device(other["id"], {"serial_number": "KML-OTHER"})

    response = await list_devices(customer.id)
    assert [d["serial_number"] for d in response.json()["results"]] == ["KML-0001"]


async def test_list_customer_devices_unknown_customer_status_code(list_devices):
    response = await list_devices(uuid.uuid4())
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("queries", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_list_customer_devices_invalid_pagination_status_code(
    list_devices, customer, queries
):
    response = await list_devices(customer.id, queries)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE", "FAULTY"])
async def test_device_status_change_status_code(update_status_device, device, status):
    response = await update_status_device(device.serial_number, status)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE", "FAULTY"])
async def test_device_status_change_data(update_status_device, device, customer, status):
    response = await update_status_device(device.serial_number, status)
    assert response.json() == {
        "id": str(device.id),
        "serial_number": device.serial_number,
        "customer_id": str(customer.id),
        "status": status,
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }


async def test_device_status_change_is_persisted(update_status_device, retrieve_device, device):
    await update_status_device(device.serial_number, "INACTIVE")
    response = await retrieve_device(device.serial_number)
    assert response.json()["status"] == "INACTIVE"


async def test_device_status_change_bumps_updated_at(update_status_device, device):
    response = await update_status_device(device.serial_number, "INACTIVE")
    assert datetime.fromisoformat(response.json()["updated_at"]) > device.updated_at


async def test_device_status_change_to_same_status_is_a_no_op(update_status_device, device):
    response = await update_status_device(device.serial_number, "ACTIVE")
    assert response.status_code == HTTPStatus.OK
    assert datetime.fromisoformat(response.json()["updated_at"]) == device.updated_at


async def test_device_status_change_unknown_device_status_code(update_status_device):
    response = await update_status_device("KML-3141592", "ACTIVE")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_device_status_change_invalid_status_status_code(update_status_device, device):
    response = await update_status_device(device.serial_number, "BROKEN")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


async def test_device_status_change_cannot_reassign_the_device(
    update_status_device, session, device, customer
):
    response = await update_status_device(
        device.serial_number, "ACTIVE", customer_id=str(uuid.uuid4())
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

    await session.refresh(device)
    assert device.customer_id == customer.id


async def test_device_of_deleted_customer_cannot_be_reactivated(
    client, update_status_device, customer, device
):
    await client.delete(f"/customers/{customer.id}")

    response = await update_status_device(device.serial_number, "ACTIVE")
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "customer_deleted"


async def test_device_of_deleted_customer_can_still_be_retrieved(
    client, retrieve_device, customer, device
):
    await client.delete(f"/customers/{customer.id}")

    response = await retrieve_device(device.serial_number)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == DeviceStatus.INACTIVE

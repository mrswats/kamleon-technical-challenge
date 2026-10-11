import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import UTC
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from sqlalchemy import func
from sqlalchemy import select

from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.ingestion.models import Measurement

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def payload(**overrides: Any) -> dict[str, Any]:
    data = {
        "type": "temperature",
        "value": 21.5,
        "unit": "celsius",
        "timestamp": T0.isoformat(),
    }
    return {**data, **overrides}


@pytest.fixture
def measurements_url(url_for):
    def _(serial_number: str) -> str:
        return url_for("ingest_measurement", serial_number=serial_number)

    return _


@pytest.fixture
def create_measurement(client, measurements_url):
    async def _(serial_number: str, data: dict[str, Any]):
        return await client.post(measurements_url(serial_number), json=data)

    return _


@pytest.fixture
def update_status(client, url_for):
    async def _(serial_number: str, status: str):
        url = url_for("change_status", serial_number=serial_number)
        return await client.patch(url, json={"status": status})

    return _


@pytest.fixture
def count_measurements(session):
    async def _() -> int:
        count = await session.scalar(select(func.count()).select_from(Measurement))
        return count or 0

    return _


def test_measurements_url(measurements_url):
    assert measurements_url("KML-0001") == "/devices/KML-0001/measurements"


async def test_measurement_create_status_code(create_measurement, device):
    response = await create_measurement(device.serial_number, payload())
    assert response.status_code == HTTPStatus.CREATED


async def test_measurement_create_data(create_measurement, device):
    response = await create_measurement(device.serial_number, payload())
    body = response.json()
    assert body == {
        "id": mock.ANY,
        "device_id": str(device.id),
        "type": "temperature",
        "value": 21.5,
        "unit": "celsius",
        "timestamp": "2026-01-01T12:00:00Z",
        "created_at": mock.ANY,
    }
    assert isinstance(body["id"], int)


async def test_measurement_create_is_stored(create_measurement, count_measurements, device):
    await create_measurement(device.serial_number, payload())
    assert await count_measurements() == 1


async def test_measurement_retry_is_idempotent_status_code(create_measurement, device):
    await create_measurement(device.serial_number, payload())
    response = await create_measurement(device.serial_number, payload())
    assert response.status_code == HTTPStatus.OK


async def test_measurement_retry_returns_the_stored_measurement(create_measurement, device):
    first = await create_measurement(device.serial_number, payload())
    retry = await create_measurement(device.serial_number, payload())
    assert retry.json() == first.json()


async def test_measurement_retry_does_not_create_duplicates(
    create_measurement, count_measurements, device
):
    for _ in range(5):
        await create_measurement(device.serial_number, payload())
    assert await count_measurements() == 1


async def test_measurement_retry_with_equivalent_timezone_is_the_same_measurement(
    create_measurement, count_measurements, device
):
    """12:00Z and 14:00+02:00 are the same instant, hence the same measurement."""
    await create_measurement(device.serial_number, payload(timestamp="2026-01-01T12:00:00Z"))
    response = await create_measurement(
        device.serial_number, payload(timestamp="2026-01-01T14:00:00+02:00")
    )
    assert response.status_code == HTTPStatus.OK
    assert await count_measurements() == 1


async def test_measurement_with_different_value_is_a_conflict(
    create_measurement, session, device, measurement
):
    response = await create_measurement(
        device.serial_number, payload(value=99.9, timestamp=measurement.timestamp.isoformat())
    )
    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "measurement_conflict"

    await session.refresh(measurement)
    assert measurement.value == 21.5  # the stored reading was not silently overwritten


async def test_measurement_with_different_unit_is_a_conflict(create_measurement, device):
    await create_measurement(device.serial_number, payload())
    response = await create_measurement(device.serial_number, payload(unit="fahrenheit"))
    assert response.status_code == HTTPStatus.CONFLICT


async def test_measurement_with_different_type_is_a_new_measurement(
    create_measurement, count_measurements, device
):
    await create_measurement(device.serial_number, payload())
    response = await create_measurement(device.serial_number, payload(type="humidity"))
    assert response.status_code == HTTPStatus.CREATED
    assert await count_measurements() == 2


async def test_measurement_with_different_timestamp_is_a_new_measurement(
    create_measurement, count_measurements, device
):
    await create_measurement(device.serial_number, payload())
    later = (T0 + timedelta(seconds=1)).isoformat()
    response = await create_measurement(device.serial_number, payload(timestamp=later))
    assert response.status_code == HTTPStatus.CREATED
    assert await count_measurements() == 2


async def test_measurement_same_reading_on_another_device_is_a_new_measurement(
    create_measurement, session, count_measurements, customer, device
):
    session.add(
        Device(serial_number="KML-0002", customer_id=customer.id, status=DeviceStatus.ACTIVE)
    )
    await session.commit()

    await create_measurement(device.serial_number, payload())
    response = await create_measurement("KML-0002", payload())
    assert response.status_code == HTTPStatus.CREATED
    assert await count_measurements() == 2


async def test_measurement_create_unknown_device_status_code(create_measurement):
    response = await create_measurement("KML-3141592", payload())
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Device not found", "code": "device_not_found"}


@pytest.mark.parametrize("status", [DeviceStatus.INACTIVE, DeviceStatus.FAULTY])
async def test_measurement_create_for_non_active_device_is_rejected(
    create_measurement, count_measurements, session, customer, status
):
    session.add(Device(serial_number="KML-OFF", customer_id=customer.id, status=status))
    await session.commit()

    response = await create_measurement("KML-OFF", payload())

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {
        "detail": "Measurements can only be ingested for ACTIVE devices",
        "code": "device_not_active",
    }
    assert await count_measurements() == 0


async def test_measurement_create_after_deactivation_is_rejected(
    create_measurement, update_status, device
):
    assert (await create_measurement(device.serial_number, payload())).status_code == 201
    await update_status(device.serial_number, "INACTIVE")

    response = await create_measurement(device.serial_number, payload(type="humidity"))
    assert response.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"type": "temperature"},
        {"value": 1.0, "unit": "celsius", "timestamp": T0.isoformat()},
        payload(type=""),
        payload(type="x" * 51),
        payload(unit=""),
        payload(value="warm"),
        payload(value=None),
        payload(timestamp="yesterday"),
        # A timestamp without a timezone is ambiguous and is rejected.
        payload(timestamp="2026-01-01T12:00:00"),
        # Unknown fields are rejected rather than silently dropped.
        {**payload(), "serial_number": "KML-0001"},
    ],
)
async def test_measurement_create_invalid_payload_status_code(create_measurement, device, data):
    response = await create_measurement(device.serial_number, data)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


@pytest.mark.parametrize("bad_number", ["NaN", "Infinity", "-Infinity"])
async def test_measurement_create_rejects_non_finite_values(
    client, measurements_url, device, bad_number
):
    body = (
        '{"type": "temperature", "value": %s, "unit": "celsius", '
        '"timestamp": "2026-01-01T12:00:00Z"}' % bad_number
    )
    response = await client.post(
        measurements_url(device.serial_number),
        content=body,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


async def test_measurement_concurrent_identical_requests_store_exactly_one(
    create_measurement, count_measurements, device
):
    """Network retries can arrive at the same time: one 201, the rest 200, a single row."""
    responses = await asyncio.gather(
        *(create_measurement(device.serial_number, payload()) for _ in range(20))
    )

    statuses = sorted(r.status_code for r in responses)
    assert statuses == [HTTPStatus.OK] * 19 + [HTTPStatus.CREATED]
    assert len({r.json()["id"] for r in responses}) == 1
    assert await count_measurements() == 1


async def test_measurement_concurrent_distinct_requests_are_all_stored(
    create_measurement, count_measurements, device
):
    responses = await asyncio.gather(
        *(
            create_measurement(
                device.serial_number, payload(timestamp=(T0 + timedelta(seconds=n)).isoformat())
            )
            for n in range(20)
        )
    )

    assert {r.status_code for r in responses} == {HTTPStatus.CREATED}
    assert await count_measurements() == 20


async def test_measurement_ingestion_racing_with_deactivation_stays_consistent(
    create_measurement, update_status, count_measurements, session, device
):
    """Every ingestion either happens-before the deactivation (201) or is refused (409).
    Never a 5xx, and never a stored measurement that was not acknowledged."""
    ingestions = [
        create_measurement(
            device.serial_number, payload(timestamp=(T0 + timedelta(seconds=n)).isoformat())
        )
        for n in range(12)
    ]
    *responses, deactivation = await asyncio.gather(
        *ingestions, update_status(device.serial_number, "INACTIVE")
    )

    assert deactivation.status_code == HTTPStatus.OK
    statuses = [r.status_code for r in responses]
    assert set(statuses) <= {HTTPStatus.CREATED, HTTPStatus.CONFLICT}
    assert await count_measurements() == statuses.count(HTTPStatus.CREATED)

    await session.refresh(device)
    assert device.status is DeviceStatus.INACTIVE
    late = await create_measurement(device.serial_number, payload(type="late"))
    assert late.status_code == HTTPStatus.CONFLICT

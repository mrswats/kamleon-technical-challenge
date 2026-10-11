from datetime import datetime
from datetime import timedelta
from datetime import UTC
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio

from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.ingestion.models import Measurement

T0 = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def hours(n: int) -> datetime:
    return T0 + timedelta(hours=n)


@pytest.fixture
def measurements_list_url(url_for):
    def _(serial_number: str) -> str:
        return url_for("list_measurements", serial_number=serial_number)

    return _


@pytest.fixture
def list_measurements(client, measurements_list_url):
    async def _(serial_number: str, queries: dict[str, Any] | None = None):
        return await client.get(measurements_list_url(serial_number), params=queries or {})

    return _


def reading(device: Device, type: str, value: float, unit: str, hour: int) -> Measurement:
    return Measurement(
        device_id=device.id,
        type=type,
        value=value,
        unit=unit,
        timestamp=hours(hour),
    )


@pytest_asyncio.fixture
async def history(session, device):
    """Temperature readings at hours 0-5 and humidity readings at hours 0-2."""
    session.add_all(
        [reading(device, "temperature", float(n), "celsius", n) for n in range(6)]
        + [reading(device, "humidity", 40.0 + n, "percent", n) for n in range(3)]
    )
    await session.commit()


def timestamps(response) -> list[str]:
    return [m["timestamp"] for m in response.json()["results"]]


def test_measurements_list_url(measurements_list_url):
    assert measurements_list_url("KML-0001") == "/devices/KML-0001/measurements"


async def test_measurement_list_status_code(list_measurements, device):
    response = await list_measurements(device.serial_number)
    assert response.status_code == HTTPStatus.OK


async def test_measurement_list_empty_data(list_measurements, device):
    response = await list_measurements(device.serial_number)
    assert response.json() == {"count": 0, "limit": 10, "offset": 0, "results": []}


async def test_measurement_list_device_not_found_status_code(list_measurements):
    response = await list_measurements("KML-3141592")
    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_measurement_list_data(list_measurements, device, measurement):
    response = await list_measurements(device.serial_number)
    assert response.json() == {
        "count": 1,
        "limit": 10,
        "offset": 0,
        "results": [
            {
                "id": measurement.id,
                "device_id": str(device.id),
                "type": "temperature",
                "value": 21.5,
                "unit": "celsius",
                "timestamp": "2026-01-01T12:00:00Z",
                "created_at": mock.ANY,
            }
        ],
    }


async def test_measurement_list_is_newest_first(list_measurements, device, history):
    response = await list_measurements(device.serial_number, {"type": "temperature"})
    assert [m["value"] for m in response.json()["results"]] == [5.0, 4.0, 3.0, 2.0, 1.0, 0.0]


async def test_measurement_list_filter_by_type_data(list_measurements, device, history):
    response = await list_measurements(device.serial_number, {"type": "humidity"})
    assert response.json()["count"] == 3
    assert {m["type"] for m in response.json()["results"]} == {"humidity"}


async def test_measurement_list_filter_by_type_no_data(list_measurements, device, measurement):
    response = await list_measurements(device.serial_number, {"type": "pressure"})
    assert response.json() == {"count": 0, "limit": 10, "offset": 0, "results": []}


async def test_measurement_list_filter_by_time_after(list_measurements, device, history):
    response = await list_measurements(
        device.serial_number,
        {"type": "temperature", "timestamp_after": hours(4).isoformat()},
    )
    assert timestamps(response) == ["2026-01-01T05:00:00Z", "2026-01-01T04:00:00Z"]


async def test_measurement_list_filter_by_time_before(list_measurements, device, history):
    response = await list_measurements(
        device.serial_number,
        {"type": "temperature", "timestamp_before": hours(1).isoformat()},
    )
    assert timestamps(response) == ["2026-01-01T01:00:00Z", "2026-01-01T00:00:00Z"]


async def test_measurement_list_filter_by_time_range_is_inclusive(
    list_measurements, device, history
):
    response = await list_measurements(
        device.serial_number,
        {
            "type": "temperature",
            "timestamp_after": hours(1).isoformat(),
            "timestamp_before": hours(3).isoformat(),
        },
    )
    assert timestamps(response) == [
        "2026-01-01T03:00:00Z",
        "2026-01-01T02:00:00Z",
        "2026-01-01T01:00:00Z",
    ]


async def test_measurement_list_filter_by_time_without_type(list_measurements, device, history):
    response = await list_measurements(
        device.serial_number,
        {"timestamp_after": hours(2).isoformat(), "timestamp_before": hours(2).isoformat()},
    )
    assert {m["type"] for m in response.json()["results"]} == {"temperature", "humidity"}
    assert response.json()["count"] == 2


async def test_measurement_list_filter_by_time_no_data(list_measurements, device, measurement):
    response = await list_measurements(
        device.serial_number, {"timestamp_after": "2026-06-01T00:00:00Z"}
    )
    assert response.json()["count"] == 0


async def test_measurement_list_time_filter_uses_measurement_time_not_ingestion_time(
    list_measurements, device, measurement
):
    """The measurement was *stored* just now but *generated* on 2026-01-01."""
    stored_after_generated = await list_measurements(
        device.serial_number, {"timestamp_before": "2026-01-02T00:00:00Z"}
    )
    assert stored_after_generated.json()["count"] == 1

    generated_after = await list_measurements(
        device.serial_number, {"timestamp_after": "2026-01-02T00:00:00Z"}
    )
    assert generated_after.json()["count"] == 0


async def test_measurement_list_time_filter_accepts_utc_offsets(
    list_measurements, device, history
):
    response = await list_measurements(
        device.serial_number,
        {"type": "temperature", "timestamp_after": "2026-01-01T07:00:00+02:00"},  # = 05:00Z
    )
    assert timestamps(response) == ["2026-01-01T05:00:00Z"]


async def test_measurement_list_pagination(list_measurements, device, history):
    first = (await list_measurements(device.serial_number, {"limit": 4})).json()
    second = (await list_measurements(device.serial_number, {"limit": 4, "offset": 4})).json()
    last = (await list_measurements(device.serial_number, {"limit": 4, "offset": 8})).json()

    assert first["count"] == second["count"] == last["count"] == 9
    assert (len(first["results"]), len(second["results"]), len(last["results"])) == (4, 4, 1)
    ids = [m["id"] for page in (first, second, last) for m in page["results"]]
    assert len(set(ids)) == 9  # no overlaps and no gaps between pages


async def test_measurement_list_only_returns_the_requested_devices_measurements(
    list_measurements, session, customer, device, measurement
):
    other = Device(serial_number="KML-0002", customer_id=customer.id, status=DeviceStatus.ACTIVE)
    session.add(other)
    await session.flush()
    session.add(reading(other, "temperature", 1.0, "celsius", 0))
    await session.commit()

    response = await list_measurements(device.serial_number)
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["id"] == measurement.id


async def test_measurement_list_invalid_time_range_status_code(list_measurements, device):
    response = await list_measurements(
        device.serial_number,
        {"timestamp_after": hours(3).isoformat(), "timestamp_before": hours(1).isoformat()},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json()["code"] == "invalid_time_range"


@pytest.mark.parametrize(
    "queries",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"timestamp_after": "yesterday"},
        # A timestamp without a timezone is ambiguous and is rejected.
        {"timestamp_after": "2026-01-01T00:00:00"},
    ],
)
async def test_measurement_list_invalid_query_status_code(list_measurements, device, queries):
    response = await list_measurements(device.serial_number, queries)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT

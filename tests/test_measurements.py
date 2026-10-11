from datetime import datetime
from datetime import timedelta
from datetime import UTC
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from django.urls import reverse


@pytest.fixture
def measurements_list_url():
    def _(serial_number: int) -> str:
        return reverse("measurements-list", kwargs={"serial_number": serial_number})

    return _


@pytest.fixture
def list_measurements(client, measurements_list_url):
    def _(serial_number: int, queries: dict[str, Any] | None = None):
        return client.get(measurements_list_url(serial_number), data=(queries or {}))

    return _


def test_measurements_list_url(measurements_list_url):
    assert measurements_list_url("31415926") == "/measurements/31415926/"


@pytest.mark.django_db
def test_measurement_list_status_code(list_measurements, device):
    response = list_measurements(device.serial_number)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_measurement_list_device_not_foundstatus_code(list_measurements):
    response = list_measurements(271828)
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.django_db
def test_measurement_list_data(list_measurements, device, measurement):
    response = list_measurements(device.serial_number)
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "m_type": "foo",
                "measurement_hash": "foobarbaz",
                "timestamp": mock.ANY,
                "unit": "ml",
                "value": [3, 1, 4, 1, 5, 9, 2, 6],
            }
        ],
    }


@pytest.mark.django_db
def test_measurement_list_filter_by_type_data(list_measurements, device, measurement):
    response = list_measurements(device.serial_number, {"m_type": "foo"})
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "m_type": "foo",
                "measurement_hash": "foobarbaz",
                "timestamp": mock.ANY,
                "unit": "ml",
                "value": [3, 1, 4, 1, 5, 9, 2, 6],
            }
        ],
    }


@pytest.mark.django_db
def test_measurement_list_filter_by_type_no_data(list_measurements, device, measurement):
    response = list_measurements(device.serial_number, {"m_type": "bar"})
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_measurement_list_filter_by_time_no_data(list_measurements, device, measurement):
    time_after = datetime.now(tz=UTC) + timedelta(days=1)
    response = list_measurements(
        device.serial_number,
        {
            "created_at_after": time_after,
        },
    )
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }


@pytest.mark.django_db
def test_measurement_list_filter_by_time_data(list_measurements, device, measurement):
    time_before = datetime.now(tz=UTC) + timedelta(days=1)
    time_after = datetime.now(tz=UTC) - timedelta(days=1)
    response = list_measurements(
        device.serial_number,
        {
            "created_at_after": time_after,
            "created_at_before": time_before,
        },
    )
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "m_type": "foo",
                "measurement_hash": "foobarbaz",
                "timestamp": mock.ANY,
                "unit": "ml",
                "value": [3, 1, 4, 1, 5, 9, 2, 6],
            }
        ],
    }

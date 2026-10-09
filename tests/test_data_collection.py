import time
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
import rq
from django.urls import reverse
from rest_framework.response import Response

from kamleon.data_collection import models
from kamleon.data_collection import tasks
from kamleon.data_collection import views


@pytest.fixture
def m_queue(f_redis):
    queue = rq.Queue("mock-default", connection=f_redis)

    with mock.patch.object(views, "default", new=queue) as m_queue:
        yield m_queue


@pytest.fixture
def measurement_url():
    return reverse("ingest-list")


@pytest.fixture
def create_measurement(client, measurement_url, m_queue):
    def _(data: dict[str, Any]) -> Response:
        return client.post(measurement_url, data=data)

    return _


def test_measurement_list_url(measurement_url):
    assert measurement_url == "/ingest/"


@pytest.mark.django_db
def test_measurement_create_status_code(create_measurement, device):
    response = create_measurement(
        {
            "serial_number": device.serial_number,
            "m_type": "foo",
            "unit": "bar",
            "value": [3, 1, 4, 1, 5],
            "timestamp": time.time(),
        }
    )
    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.django_db
def test_measurement_create_data(create_measurement, device):
    timestamp = time.time()
    response = create_measurement(
        {
            "serial_number": device.serial_number,
            "m_type": "foo",
            "unit": "bar",
            "value": [3, 1, 4, 1, 5],
            "timestamp": timestamp,
        }
    )
    assert response.json() == {
        "m_type": "foo",
        "timestamp": timestamp,
        "value": [3, 1, 4, 1, 5],
        "unit": "bar",
    }


@pytest.mark.django_db
def test_measurement_create_task_is_idempotent(device):
    hash = 314159262
    data = {
        "device": device,
        "m_type": "foo",
        "unit": "bar",
        "value": [3, 1, 4, 1, 5],
        "timestamp": time.time(),
        "measurement_hash": hash,
    }
    tasks.process_measurement(data)
    tasks.process_measurement(data)
    assert models.Measurement.objects.filter(measurement_hash=hash).count() == 1

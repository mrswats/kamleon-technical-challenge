import time
from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
import rq
from django.urls import reverse
from rest_framework.response import Response

from kamleon.ingestion import models
from kamleon.ingestion import tasks
from kamleon.ingestion import views


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
def test_measurement_create_enqueues_task(create_measurement, device, m_queue):
    create_measurement(
        {
            "serial_number": device.serial_number,
            "m_type": "foo",
            "unit": "bar",
            "value": [3, 1, 4, 1, 5],
            "timestamp": time.time(),
        }
    )

    assert len(m_queue.jobs) == 1


@pytest.mark.django_db
def test_measurement_create_task_is_idempotent(device):
    hash = 314159262
    data = {
        "m_type": "foo",
        "unit": "bar",
        "value": [3, 1, 4, 1, 5],
        "timestamp": time.time(),
    }
    tasks.process_measurement(device.serial_number, hash, data)
    tasks.process_measurement(device.serial_number, hash, data)
    assert models.Measurement.objects.filter(measurement_hash=hash).count() == 1


@pytest.mark.django_db
def test_measurement_create_task_raises_error_for_unexisting_devices():
    hash = 314159262
    data = {
        "m_type": "foo",
        "unit": "bar",
        "value": [3, 1, 4, 1, 5],
        "timestamp": time.time(),
    }

    with pytest.raises(tasks.IngestionError) as exc:
        tasks.process_measurement(314159262, hash, data)

    assert exc.value.args == ("Device not found",)

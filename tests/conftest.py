import time

import fakeredis
import pytest
from rest_framework.test import APIClient

from kamleon.devices import models as device_models
from kamleon.identity import models as identity_models
from kamleon.ingestion import models as ingestion_models


@pytest.fixture
def customer():
    return identity_models.Customer.objects.create(
        name="Steve",
        email="steve@example.com",
        username="steve",
    )


@pytest.fixture
def device(customer) -> device_models.Device:
    return device_models.Device.objects.create(
        customer=customer,
        status="ACTIVE",
    )


@pytest.fixture
def measurement(device) -> ingestion_models.Measurement:
    return ingestion_models.Measurement.objects.create(
        device=device,
        measurement_hash="foobarbaz",
        m_type="foo",
        value=[3, 1, 4, 1, 5, 9, 2, 6],
        unit="ml",
        timestamp=time.time(),
    )


@pytest.fixture
def client(customer):
    c = APIClient()
    c.force_authenticate(customer)
    return c


@pytest.fixture
def f_redis():
    return fakeredis.FakeStrictRedis()

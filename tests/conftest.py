import fakeredis
import pytest
from rest_framework.test import APIClient

from kamleon.devices import models as device_models
from kamleon.identity import models as identity_models


@pytest.fixture
def user() -> identity_models.User:
    return identity_models.User.objects.create(
        username="Steve",
    )


@pytest.fixture
def customer(user):
    return identity_models.Customer.objects.create(
        user=user,
    )


@pytest.fixture
def device(customer) -> device_models.Device:
    return device_models.Device.objects.create(
        customer=customer,
        status="ACTIVE",
    )


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def f_redis():
    return fakeredis.FakeStrictRedis()

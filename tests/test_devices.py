from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from django.urls import reverse


@pytest.fixture
def device_list_url():
    return reverse("device-list")


@pytest.fixture
def device_detail_url():
    def _(device_serial_number: int) -> str:
        return reverse(
            "device-detail",
            kwargs={"serial_number": device_serial_number},
        )

    return _


@pytest.fixture
def device_detail_status_change_url():
    def _(device_serial_number: int) -> str:
        return reverse(
            "device-change-status",
            kwargs={"serial_number": device_serial_number},
        )

    return _


@pytest.fixture
def create_device(client, device_list_url):
    def _(data: dict[str, Any]):
        return client.post(device_list_url, data=data)

    return _


@pytest.fixture
def retrieve_device(client, device_detail_url):
    def _(serial_number: int):
        return client.get(device_detail_url(serial_number))

    return _


@pytest.fixture
def update_status_device(client, device_detail_status_change_url):
    def _(serial_number: int, status: str):
        return client.patch(
            device_detail_status_change_url(serial_number),
            data={"status": status},
        )

    return _


def test_device_list_url(device_list_url):
    assert device_list_url == "/devices/"


def test_device_detail_url(device_detail_url):
    assert device_detail_url("3141592") == "/devices/3141592/"


def test_device_status_change_url(device_detail_status_change_url):
    assert device_detail_status_change_url("3141592") == "/devices/3141592/status/"


@pytest.mark.django_db
def test_retrieve_device_status_code(retrieve_device, device):
    response = retrieve_device(device.serial_number)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_retrieve_device_data(retrieve_device, device):
    response = retrieve_device(device.serial_number)
    assert response.json() == {
        "serial_number": device.serial_number,
        "status": "ACTIVE",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }


@pytest.mark.django_db
def test_create_device_status_code(create_device, customer):
    response = create_device({"customer": customer.id})
    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.django_db
def test_create_device_data(create_device, customer):
    response = create_device({"customer": customer.id})
    assert response.json() == {
        "serial_number": mock.ANY,
        "status": "INACTIVE",
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE"])
@pytest.mark.django_db
def test_device_status_change_status_code(update_status_device, device, status):
    response = update_status_device(device.serial_number, status)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.parametrize("status", ["ACTIVE", "INACTIVE"])
@pytest.mark.django_db
def test_device_status_change_data(update_status_device, device, status):
    response = update_status_device(device.serial_number, status)
    assert response.json() == {
        "serial_number": device.serial_number,
        "status": status,
        "created_at": mock.ANY,
        "updated_at": mock.ANY,
    }

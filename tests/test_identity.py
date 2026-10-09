from http import HTTPStatus
from typing import Any
from unittest import mock

import pytest
from django.urls import reverse


@pytest.fixture
def identity_list_url():
    return reverse("identity-list")


@pytest.fixture
def identity_detail_url():
    def _(customer_id: str) -> str:
        return reverse("identity-detail", kwargs={"kid": customer_id})

    return _


@pytest.fixture
def create_customer(client, identity_list_url):
    def _(data: dict[str, Any]):
        return client.post(identity_list_url, data=data)

    return _


@pytest.fixture
def retrieve_customer(client, identity_detail_url):
    def _(customer_id: str):
        return client.get(identity_detail_url(customer_id))

    return _


def test_identity_list_url(identity_list_url):
    assert identity_list_url == "/customers/"


def test_identity_detail_url(identity_detail_url):
    assert identity_detail_url("foo-bar") == "/customers/foo-bar/"


@pytest.mark.django_db
def test_identity_retrieve_customer_status_code(retrieve_customer, customer):
    response = retrieve_customer(customer.kid)
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_identity_retrieve_customer_data(retrieve_customer, customer):
    response = retrieve_customer(customer.kid)
    assert response.json() == {
        "created_at": mock.ANY,
        "kid": mock.ANY,
        "updated_at": mock.ANY,
        "user": {
            "email": "",
            "username": "Steve",
            "first_name": "",
            "last_name": "",
        },
    }


@pytest.mark.django_db
def test_identity_create_customer_status_code(create_customer):
    response = create_customer(
        {
            "user": {
                "username": "Katie",
                "password": "badpassword",
            }
        }
    )
    assert response.status_code == HTTPStatus.CREATED


@pytest.mark.django_db
def test_identity_create_customer_data(create_customer):
    response = create_customer(
        {
            "user": {
                "username": "Katie",
                "password": "badpassword",
            }
        }
    )
    assert response.json() == {
        "created_at": mock.ANY,
        "kid": mock.ANY,
        "updated_at": mock.ANY,
        "user": {
            "email": "",
            "username": "Katie",
            "first_name": "",
            "last_name": "",
        },
    }

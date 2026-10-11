import uuid
from datetime import datetime
from datetime import UTC

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from kamleon.devices.models import Device
from kamleon.identity.models import Customer
from kamleon.ingestion.models import Measurement


async def test_customer_emails_are_unique(session, customer):
    session.add(Customer(name="Clone", email=customer.email))
    with pytest.raises(IntegrityError, match="uq_customers_email"):
        await session.commit()


async def test_device_serial_numbers_are_unique(session, customer, device):
    session.add(Device(serial_number=device.serial_number, customer_id=customer.id))
    with pytest.raises(IntegrityError, match="uq_devices_serial_number"):
        await session.commit()


async def test_a_device_needs_a_customer(session):
    session.add(Device(serial_number="KML-ORPHAN", customer_id=None))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_device_status_is_restricted_to_known_values(session, customer):
    insert = text(
        "INSERT INTO devices (id, serial_number, customer_id, status) "
        "VALUES (gen_random_uuid(), 'KML-BAD', :customer_id, 'BROKEN')"
    )
    with pytest.raises(IntegrityError, match="ck_devices_device_status"):
        await session.execute(insert, {"customer_id": customer.id})


async def test_a_measurement_is_unique_per_device_type_and_timestamp(session, device, measurement):
    session.add(
        Measurement(
            device_id=device.id,
            type=measurement.type,
            value=1.0,
            unit="celsius",
            timestamp=measurement.timestamp,
        )
    )
    with pytest.raises(IntegrityError, match="uq_measurements_device_id_type_timestamp"):
        await session.commit()


async def test_a_measurement_needs_an_existing_device(session):
    # random id: no such device
    session.add(
        Measurement(
            device_id=uuid.uuid4(),
            type="temperature",
            value=1.0,
            unit="celsius",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_a_customer_with_devices_cannot_be_hard_deleted(session, customer, device):
    with pytest.raises(IntegrityError, match="fk_devices_customer_id_customers"):
        await session.execute(text("DELETE FROM customers"))


async def test_a_device_with_measurements_cannot_be_hard_deleted(session, device, measurement):
    with pytest.raises(IntegrityError, match="fk_measurements_device_id_devices"):
        await session.execute(text("DELETE FROM devices"))

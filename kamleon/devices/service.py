import uuid
from collections.abc import Sequence

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kamleon.db import violated_constraint
from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.devices.schemas import DeviceCreate
from kamleon.errors import CustomerDeletedError
from kamleon.errors import CustomerNotFoundError
from kamleon.errors import DeviceNotFoundError
from kamleon.errors import DuplicateSerialNumberError
from kamleon.identity.models import Customer
from kamleon.pagination import Pagination


async def register_device(
    session: AsyncSession,
    customer_id: uuid.UUID,
    data: DeviceCreate,
) -> Device:
    # FOR SHARE on the customer: many registrations can proceed together, but not while
    # the customer is being deleted (which takes FOR UPDATE).
    customer = await session.scalar(
        select(Customer)
        .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        .with_for_update(read=True)
    )
    if customer is None:
        raise CustomerNotFoundError

    device = Device(serial_number=data.serial_number, customer_id=customer.id, status=data.status)
    session.add(device)
    try:
        await session.commit()
    except IntegrityError as exc:
        # The UNIQUE constraint is the source of truth for serial numbers, so two concurrent
        # registrations of the same serial cannot both succeed.
        await session.rollback()
        if violated_constraint(exc) == "uq_devices_serial_number":
            raise DuplicateSerialNumberError from exc
        raise  # pragma: no cover
    return device


async def get_device(session: AsyncSession, serial_number: str) -> Device:
    device = await session.scalar(select(Device).where(Device.serial_number == serial_number))
    if device is None:
        raise DeviceNotFoundError
    return device


async def list_customer_devices(
    session: AsyncSession,
    customer_id: uuid.UUID,
    pagination: Pagination,
) -> tuple[int, Sequence[Device]]:
    customer_exists = await session.scalar(
        select(Customer.id).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
    )
    if customer_exists is None:
        raise CustomerNotFoundError

    count = await session.scalar(
        select(func.count()).select_from(Device).where(Device.customer_id == customer_id)
    )
    devices = await session.scalars(
        select(Device)
        .where(Device.customer_id == customer_id)
        .order_by(Device.created_at, Device.id)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return count or 0, devices.all()


async def change_status(
    session: AsyncSession,
    serial_number: str,
    status: DeviceStatus,
) -> Device:
    device = await get_device(session, serial_number)

    if status is DeviceStatus.ACTIVE:
        # A device of a deleted customer must stay inactive. Lock order is customer first,
        # then device, the same as `delete_customer`, so the two cannot deadlock.
        customer = await session.scalar(
            select(Customer).where(Customer.id == device.customer_id).with_for_update(read=True)
        )
        if customer is None or customer.deleted_at is not None:
            raise CustomerDeletedError

    # Re-read the device under an exclusive lock. This waits for in-flight measurement
    # ingestions (FOR SHARE) to commit, so once this transaction commits no further
    # measurement can be accepted for a device that is no longer ACTIVE.
    await session.refresh(device, with_for_update=True)
    if device.status is not status:
        device.status = status
    await session.commit()
    return device

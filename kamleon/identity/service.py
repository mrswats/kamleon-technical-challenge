import uuid
from datetime import datetime
from datetime import UTC

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kamleon.db import violated_constraint
from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.errors import CustomerNotFoundError
from kamleon.errors import DuplicateEmailError
from kamleon.identity.models import Customer
from kamleon.identity.schemas import CustomerCreate

ANONYMISED_NAME = "Deleted customer"


async def create_customer(session: AsyncSession, data: CustomerCreate) -> Customer:
    customer = Customer(name=data.name, email=data.email)
    session.add(customer)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if violated_constraint(exc) == "uq_customers_email":
            raise DuplicateEmailError from exc
        raise  # pragma: no cover
    return customer


async def get_customer(session: AsyncSession, customer_id: uuid.UUID) -> Customer:
    customer = await session.scalar(
        select(Customer).where(Customer.id == customer_id, Customer.deleted_at.is_(None))
    )
    if customer is None:
        raise CustomerNotFoundError
    return customer


async def delete_customer(session: AsyncSession, customer_id: uuid.UUID) -> None:
    """Delete a customer in the GDPR sense: erase the personal data, keep the rest.

    * The customer row is kept and its name and email are anonymised, so devices and
      their measurements stay intact (they are operational data, and the foreign keys are
      ON DELETE RESTRICT so they can never be removed by accident).
    * The customer's devices are deactivated so they stop ingesting data.
    * Everything happens in one transaction. The customer row is locked first (FOR UPDATE),
      which serialises this against concurrent device registration and device activation
      (both take a FOR SHARE lock on the customer), and the device UPDATE waits for any
      in-flight measurement ingestion (which holds FOR SHARE on its device).
    """
    customer = await session.scalar(
        select(Customer)
        .where(Customer.id == customer_id, Customer.deleted_at.is_(None))
        .with_for_update()
    )
    if customer is None:
        raise CustomerNotFoundError

    customer.name = ANONYMISED_NAME
    customer.email = f"deleted-{customer.id}@anonymised.invalid"
    customer.deleted_at = datetime.now(UTC)
    await session.execute(
        update(Device)
        .where(Device.customer_id == customer.id, Device.status != DeviceStatus.INACTIVE)
        .values(status=DeviceStatus.INACTIVE)
    )
    await session.commit()

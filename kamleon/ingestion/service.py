from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from kamleon.devices.models import Device
from kamleon.devices.models import DeviceStatus
from kamleon.errors import DeviceNotActiveError
from kamleon.errors import DeviceNotFoundError
from kamleon.errors import InvalidTimeRangeError
from kamleon.errors import MeasurementConflictError
from kamleon.ingestion.models import Measurement
from kamleon.ingestion.models import UNIQUE_MEASUREMENT
from kamleon.ingestion.schemas import MeasurementCreate
from kamleon.pagination import Pagination


@dataclass(frozen=True)
class IngestResult:
    measurement: Measurement
    created: bool


async def ingest_measurement(
    session: AsyncSession,
    serial_number: str,
    data: MeasurementCreate,
) -> IngestResult:
    """Store a measurement exactly once, however many times the request is retried.

    1. The device row is locked FOR SHARE. Concurrent ingestions do not block each other,
       but a concurrent status change (UPDATE ... FOR UPDATE) waits for us to commit, and we
       wait for it. So the "device is ACTIVE" check below stays true until we commit.
    2. `INSERT ... ON CONFLICT DO NOTHING` on the natural key is a single atomic statement:
       there is no check-then-insert window for two retries to slip through.
    3. If the row already existed, the retry is acknowledged (200) when it carries the same
       value and unit, and rejected (409) when it contradicts the stored reading, so a
       corrected value is never silently dropped.
    """
    device = await session.scalar(
        select(Device).where(Device.serial_number == serial_number).with_for_update(read=True)
    )
    if device is None:
        raise DeviceNotFoundError
    if device.status is not DeviceStatus.ACTIVE:
        raise DeviceNotActiveError

    insert_stmt = (
        insert(Measurement)
        .values(
            device_id=device.id,
            type=data.type,
            value=data.value,
            unit=data.unit,
            timestamp=data.timestamp,
        )
        .on_conflict_do_nothing(constraint=UNIQUE_MEASUREMENT)
        .returning(Measurement)
    )
    created = await session.scalar(
        select(Measurement).from_statement(insert_stmt).execution_options(populate_existing=True)
    )
    if created is not None:
        await session.commit()
        return IngestResult(measurement=created, created=True)

    existing = await session.scalar(
        select(Measurement).where(
            Measurement.device_id == device.id,
            Measurement.type == data.type,
            Measurement.timestamp == data.timestamp,
        )
    )
    assert existing is not None  # the conflict proves the row exists (rows are never deleted)
    if existing.value != data.value or existing.unit != data.unit:
        raise MeasurementConflictError
    await session.commit()
    return IngestResult(measurement=existing, created=False)


async def list_measurements(
    session: AsyncSession,
    serial_number: str,
    *,
    measurement_type: str | None,
    timestamp_after: datetime | None,
    timestamp_before: datetime | None,
    pagination: Pagination,
) -> tuple[int, Sequence[Measurement]]:
    if (
        timestamp_after is not None
        and timestamp_before is not None
        and timestamp_after > timestamp_before
    ):
        raise InvalidTimeRangeError

    device_id = await session.scalar(
        select(Device.id).where(Device.serial_number == serial_number)
    )
    if device_id is None:
        raise DeviceNotFoundError

    # The time range filters on the measurement's own `timestamp` (when it was generated),
    # not on `created_at` (when we received it). Both bounds are inclusive.
    conditions = [Measurement.device_id == device_id]
    if measurement_type is not None:
        conditions.append(Measurement.type == measurement_type)
    if timestamp_after is not None:
        conditions.append(Measurement.timestamp >= timestamp_after)
    if timestamp_before is not None:
        conditions.append(Measurement.timestamp <= timestamp_before)

    count = await session.scalar(select(func.count()).select_from(Measurement).where(*conditions))
    measurements = await session.scalars(
        select(Measurement)
        .where(*conditions)
        .order_by(Measurement.timestamp.desc(), Measurement.id.desc())
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    return count or 0, measurements.all()

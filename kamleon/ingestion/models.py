import uuid
from datetime import datetime

from sqlalchemy import BigInteger
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy import Index
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kamleon.db import Base

# The natural key of a measurement. It is what makes ingestion idempotent: a device reports
# at most one value per measurement type per instant, so a retried request hits this
# constraint instead of creating a duplicate. (It also serves the common read query
# "device + type + time range" as an index.)
UNIQUE_MEASUREMENT = "uq_measurements_device_id_type_timestamp"


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("device_id", "type", "timestamp"),
        # Serves "all measurements of a device in a time range" (no type filter) and
        # newest-first ordering; the unique index above cannot because `type` sits between.
        Index("ix_measurements_device_id_timestamp", "device_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # RESTRICT: measurements are never silently deleted along with a device.
    device_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("devices.id", ondelete="RESTRICT"),
    )
    type: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    # When the device generated the reading (UTC instant). `created_at` is when we stored it.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

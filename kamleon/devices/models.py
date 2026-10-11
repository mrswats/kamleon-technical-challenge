import enum
import uuid

from sqlalchemy import CheckConstraint
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kamleon.db import Base
from kamleon.db import TimestampMixin


class DeviceStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FAULTY = "FAULTY"


class Device(TimestampMixin, Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE', 'FAULTY')",
            name="device_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Chosen by the caller (it is the factory serial printed on the product), not generated.
    serial_number: Mapped[str] = mapped_column(String(64), unique=True)
    # RESTRICT: a customer that still has devices can never be hard-deleted by accident.
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            name="device_status",
            native_enum=False,
            length=16,
            create_constraint=False,
            validate_strings=True,
        ),
        default=DeviceStatus.INACTIVE,
    )

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import StringConstraints

from kamleon.devices.models import DeviceStatus


class DeviceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"serial_number": "KML-000123"}]},
    )

    serial_number: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=64,
            pattern=r"^[A-Za-z0-9._-]+$",
        ),
    ]
    status: DeviceStatus = DeviceStatus.INACTIVE


class DeviceStatusUpdate(BaseModel):
    # Only the status is writable here. In particular a device cannot be moved to another
    # customer through this endpoint (extra fields are rejected).
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"status": "ACTIVE"}]},
    )

    status: DeviceStatus


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    serial_number: str
    customer_id: uuid.UUID
    status: DeviceStatus
    created_at: datetime
    updated_at: datetime

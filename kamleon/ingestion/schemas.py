import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class MeasurementCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "type": "temperature",
                    "value": 21.5,
                    "unit": "celsius",
                    "timestamp": "2026-01-01T12:00:00Z",
                }
            ]
        },
    )

    type: ShortText
    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: ShortText
    # Timezone-aware on purpose: a naive timestamp is ambiguous and is rejected.
    timestamp: AwareDatetime


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: uuid.UUID
    type: str
    value: float
    unit: str
    timestamp: datetime
    created_at: datetime

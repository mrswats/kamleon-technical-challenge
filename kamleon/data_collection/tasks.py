from typing import Any

from kamleon.data_collection import models
from kamleon.devices import models as device_models


class IngestionError(Exception):
    pass


def process_measurement(
    serial_number: int,
    measurement_hash: int,
    data: dict[str, Any],
) -> None:
    device = device_models.Device.objects.filter(
        serial_number=serial_number,
        status="ACTIVE",
    ).first()

    if device is None:
        raise IngestionError("Device not found")

    models.Measurement.objects.get_or_create(
        device=device,
        measurement_hash=measurement_hash,
        **data,
    )

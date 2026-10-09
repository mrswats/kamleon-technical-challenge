from typing import Any

from kamleon.data_collection import models


def process_measurement(data: dict[str, Any]) -> None:
    models.Measurement.objects.get_or_create(**data)

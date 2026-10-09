from rest_framework.generics import get_object_or_404
from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import GenericViewSet

from kamleon.data_collection import models
from kamleon.data_collection import serializers
from kamleon.data_collection.queues import default
from kamleon.data_collection.tasks import process_measurement
from kamleon.devices import models as device_models


class MeasurementViewSet(CreateModelMixin, GenericViewSet):
    queryset = models.Measurement.objects.all()
    serializer_class = serializers.MeasurementSerializer

    def perform_create(self, serializer: serializers.MeasurementSerializer) -> None:
        serial_number = serializer.validated_data.pop("serial_number")
        timestamp = serializer.validated_data["timestamp"]

        device = get_object_or_404(
            device_models.Device,
            serial_number=serial_number,
            status="ACTIVE",
        )

        default.enqueue(
            process_measurement,
            {
                **serializer.validated_data,
                "device": device,
                "measurement_hash": hash(f"{serial_number}{timestamp}"),
            },
        )

from rest_framework.mixins import CreateModelMixin
from rest_framework.viewsets import GenericViewSet

from kamleon.ingestion import models
from kamleon.ingestion import serializers
from kamleon.ingestion.queues import default
from kamleon.ingestion.tasks import process_measurement


class MeasurementViewSet(CreateModelMixin, GenericViewSet):
    queryset = models.Measurement.objects.all()
    serializer_class = serializers.MeasurementSerializer

    def perform_create(self, serializer: serializers.MeasurementSerializer) -> None:
        serial_number = serializer.validated_data.pop("serial_number")
        timestamp = serializer.validated_data["timestamp"]

        measurement_hash = hash(f"{serial_number}{timestamp}")

        default.enqueue(
            process_measurement,
            serial_number=serial_number,
            measurement_hash=measurement_hash,
            data=serializer.validated_data,
        )

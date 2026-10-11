import hashlib

from django.db.models.query import QuerySet
from django_filters import rest_framework as filters
from rest_framework import generics
from rest_framework import mixins
from rest_framework import viewsets

from kamleon.devices import models as devices_models
from kamleon.ingestion import models
from kamleon.ingestion import serializers
from kamleon.ingestion.queues import default
from kamleon.ingestion.tasks import process_measurement


class MeasurementIngestionViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = models.Measurement.objects.all()
    serializer_class = serializers.MeasurementSerializer

    def perform_create(self, serializer: serializers.MeasurementSerializer) -> None:
        serial_number = serializer.validated_data.pop("serial_number")
        measurement_type = serializer.validated_data["m_type"]
        measurement_unit = serializer.validated_data["unit"]
        timestamp = serializer.validated_data["timestamp"]

        measurement_hash = hashlib.sha256(
            f"{serial_number}{measurement_type}{measurement_unit}{timestamp}".encode()
        )

        default.enqueue(
            process_measurement,
            serial_number=serial_number,
            measurement_hash=measurement_hash.hexdigest(),
            data=serializer.validated_data,
        )


class MeasurementFilterSet(filters.FilterSet):
    created_at = filters.DateTimeFromToRangeFilter()

    class Meta:
        model = models.Measurement
        fields = (
            "m_type",
            "created_at",
        )


class MeasurementViewSet(generics.ListAPIView):
    queryset = models.Measurement.objects.all()
    serializer_class = serializers.MeasurementSerializer
    lookup_field = "kuid"
    related_lookup_field = "serial_number"
    filterset_class = MeasurementFilterSet

    def get_queryset(self) -> QuerySet[models.Measurement]:
        device = generics.get_object_or_404(
            devices_models.Device,
            serial_number=self.kwargs[self.related_lookup_field],
        )
        return self.queryset.filter(device=device)

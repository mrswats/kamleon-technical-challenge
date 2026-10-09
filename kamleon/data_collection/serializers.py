from rest_framework import serializers

from kamleon.data_collection import models


class MeasurementSerializer(serializers.ModelSerializer):
    serial_number = serializers.IntegerField(write_only=True)

    class Meta:
        model = models.Measurement
        fields = (
            "m_type",
            "measurement_hash",
            "serial_number",
            "timestamp",
            "unit",
            "value",
        )
        extra_kwargs = {
            "measurement_hash": {
                "read_only": True,
            }
        }

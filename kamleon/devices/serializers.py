from rest_framework import serializers

from kamleon.devices import models


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Device
        fields = (
            "created_at",
            "customer",
            "serial_number",
            "status",
            "updated_at",
        )
        extra_kwargs = {
            "customer": {
                "write_only": True,
            },
        }


class DeviceStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Device
        fields = (
            "created_at",
            "customer",
            "serial_number",
            "status",
            "updated_at",
        )
        extra_kwargs = {
            "serial_number": {
                "read_only": True,
            },
            "updated_at": {
                "read_only": True,
            },
            "created_at": {
                "read_only": True,
            },
            "customer": {
                "write_only": True,
            },
        }

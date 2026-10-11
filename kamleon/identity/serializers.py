from rest_framework import serializers

from kamleon.identity import models


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Customer
        fields = (
            "created_at",
            "email",
            "kid",
            "name",
            "password",
            "updated_at",
            "username",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
            },
        }

from rest_framework import serializers

from kamleon.identity import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.User
        fields = (
            "email",
            "password",
            "username",
            "first_name",
            "last_name",
        )
        extra_kwargs = {
            "password": {
                "write_only": True,
            },
            "first_name": {
                "required": False,
            },
            "last_name": {
                "required": False,
            },
        }


class CustomerSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = models.Customer
        fields = (
            "created_at",
            "kid",
            "updated_at",
            "user",
        )

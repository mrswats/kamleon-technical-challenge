from rest_framework import mixins
from rest_framework import viewsets

from kamleon.identity import models
from kamleon.identity import serializers


class CustomerViewSet(
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Customer.objects.all()
    serializer_class = serializers.CustomerSerializer
    lookup_field = "kid"

    def perform_create(self, serializer: serializers.CustomerSerializer) -> None:
        user_data = serializer.validated_data.pop("user")
        user = models.User.objects.create_user(**user_data)
        serializer.save(
            user=user,
        )

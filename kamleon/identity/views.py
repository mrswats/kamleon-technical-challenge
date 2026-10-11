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

from http import HTTPMethod

from rest_framework import decorators
from rest_framework import mixins
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer

from kamleon.devices import models
from kamleon.devices import serializers


class DeviceViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = models.Device.objects.all()
    serializer_class = serializers.DeviceSerializer
    lookup_field = "serial_number"

    def get_serializer_class(self) -> type[Serializer]:
        if self.action == "change_status":
            return serializers.DeviceStatusSerializer

        return serializers.DeviceSerializer

    @decorators.action(
        methods=[HTTPMethod.PATCH],
        detail=True,
        url_name="change-status",
        url_path="status",
    )
    def change_status(self, request: Request, serial_number: int) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

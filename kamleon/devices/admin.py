from django.contrib import admin

from kamleon.devices import models


@admin.register(models.Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "serial_number",
        "status",
        "created_at",
        "updated_at",
    )

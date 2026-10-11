from django.contrib import admin

from kamleon.ingestion import models


@admin.register(models.Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "measurement_hash",
        "kuid",
        "timestamp",
        "m_type",
        "unit",
        "value",
        "created_at",
        "updated_at",
    )

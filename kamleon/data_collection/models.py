import uuid

from django.db import models


class Measurement(models.Model):
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.DO_NOTHING,
        verbose_name="measurements",
    )
    measurement_hash = models.PositiveIntegerField(
        unique=True,
    )
    kuid = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
    )
    m_type = models.CharField(max_length=50)
    value = models.JSONField()
    unit = models.CharField(max_length=50)
    timestamp = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

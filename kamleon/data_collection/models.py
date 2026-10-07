from django.db import models


class Measurement(models.Model):
    device = models.ForeignKey(
        "devices.Device",
        on_delete=models.DO_NOTHING,
        verbose_name="measurements",
    )
    m_type = models.CharField(max_length=50)
    value = models.JSONField(default=list)
    unit = models.CharField(max_length=50)
    timestamp = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

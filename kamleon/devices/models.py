from django.db import models


class StatusChoices(models.TextChoices):
    active = ("ACTIVE", "Active")
    inactive = ("INACTIVE", "Inactive")
    faulty = ("FAULTY", "Faulty")


class Device(models.Model):
    serial_number = models.CharField(max_length=50)
    customer = models.ForeignKey(
        "identity.Customer",
        on_delete=models.DO_NOTHING,
        verbose_name="devices",
    )
    status = models.CharField(
        max_length=50,
        choices=StatusChoices,
        default=StatusChoices.inactive,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

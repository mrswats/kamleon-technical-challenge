import random

from django.db import models


def default_serial_number() -> int:
    return random.randint(100_000_000, 999_999_999)


class StatusChoices(models.TextChoices):
    active = ("ACTIVE", "Active")
    inactive = ("INACTIVE", "Inactive")
    faulty = ("FAULTY", "Faulty")


class Device(models.Model):
    customer = models.ForeignKey(
        "identity.Customer",
        on_delete=models.DO_NOTHING,
        verbose_name="devices",
    )
    serial_number = models.PositiveIntegerField(
        default=default_serial_number,
        unique=True,
        db_index=True,
    )
    status = models.CharField(
        max_length=50,
        choices=StatusChoices,
        default=StatusChoices.inactive,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

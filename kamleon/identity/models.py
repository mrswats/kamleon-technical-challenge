import uuid

from django.contrib.auth import models as auth_models
from django.db import models


class User(auth_models.AbstractUser):
    pass


class Customer(models.Model):
    user = models.OneToOneField(
        "identity.User",
        on_delete=models.DO_NOTHING,
        verbose_name="customer",
    )
    kid = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

import uuid

from django.contrib.auth import models as auth_models
from django.db import models
from django.utils.translation import gettext_lazy as _


class Customer(auth_models.AbstractUser):
    email = models.EmailField(_("email address"))
    name = models.CharField(_("first name"), max_length=150)
    kid = models.UUIDField(default=uuid.uuid4, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

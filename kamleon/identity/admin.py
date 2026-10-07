from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from kamleon.identity.models import User

admin.site.register(User, UserAdmin)
# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from kamleon.identity.models import Customer

admin.site.register(Customer, UserAdmin)

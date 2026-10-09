from django.contrib import admin
from django.urls import include
from django.urls import path

urlpatterns = [
    path("docs/", include("django_simple_docs.urls")),
    path("admin/", admin.site.urls),
    path("", include("kamleon.identity.urls")),
    path("", include("kamleon.data_collection.urls")),
]

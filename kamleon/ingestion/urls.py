from django.urls import path
from rest_framework import routers

from kamleon.ingestion import views

router = routers.SimpleRouter()
router.register("ingest", views.MeasurementIngestionViewSet, basename="ingest")


urlpatterns = [
    *router.urls,
    path(
        "measurements/<int:serial_number>/",
        views.MeasurementViewSet.as_view(),
        name="measurements-list",
    ),
]

from rest_framework import routers

from kamleon.ingestion import views

router = routers.SimpleRouter()
router.register("ingest", views.MeasurementViewSet, basename="ingest")


urlpatterns = router.urls

from rest_framework import routers

from kamleon.devices import views

router = routers.SimpleRouter()
router.register("devices", views.DeviceViewSet, basename="device")


urlpatterns = router.urls

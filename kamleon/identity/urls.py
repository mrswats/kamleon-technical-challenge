from rest_framework import routers

from kamleon.identity import views

router = routers.SimpleRouter()
router.register("customers", views.CustomerViewSet, basename="identity")

urlpatterns = router.urls

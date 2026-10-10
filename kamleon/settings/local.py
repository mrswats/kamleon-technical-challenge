from kamleon.settings.base import *  # noqa: F401,F403
from kamleon.settings.base import BASE_DIR
from kamleon.settings.base import INSTALLED_APPS

SECRET_KEY = "django-insecure-bk+f5v(+y&f^i^g2jr4_4(rk2jc#nqo6rn2i64di6n#(vzr+4e"

DEBUG = True

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "kamleon.db",
    }
}

INSTALLED_APPS.append("django_extensions")

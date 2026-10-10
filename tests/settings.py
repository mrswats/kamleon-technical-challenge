from kamleon.settings.base import *  # noqa: F401,F403

SECRET_KEY = "django-insecure-bk+f5v(+y&f^i^g2jr4_4(rk2jc#nqo6rn2i64di6n#(vzr+4e"

DEBUG = False

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

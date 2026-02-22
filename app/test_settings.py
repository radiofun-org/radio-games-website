import os

os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "contacts"]

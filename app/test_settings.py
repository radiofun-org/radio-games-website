import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from app.settings import *  # noqa: F401, F403

SESSION_ENGINE: str = "django.contrib.sessions.backends.db"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

import os

from pathlib import Path

import dj_database_url
import sentry_sdk

from env_tools import env_to_bool

BASE_DIR = Path(__file__).resolve().parent.parent

IS_PRODUCTION = os.getenv("ENV") == "production"

SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment="production" if IS_PRODUCTION else "development",
        release=os.getenv("SOURCE_COMMIT"),
        send_default_pii=False,
        traces_sample_rate=0.0,
    )

DEBUG = env_to_bool("DEBUG") and not IS_PRODUCTION

if IS_PRODUCTION:
    SECURE_HSTS_SECONDS = 3600

SECRET_KEY = os.getenv("SECRET_KEY")

SECURE_SSL_REDIRECT = IS_PRODUCTION

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Sessions read from the Redis cache but are backed by the database, so a
# Redis restart or eviction doesn't log everyone out.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# 127.0.0.1 is for the container healthcheck.
ALLOWED_HOSTS = ["radio.games", "127.0.0.1"] if IS_PRODUCTION else ["*"]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

INSTALLED_APPS = [
    "anymail",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.humanize",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django_extensions",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "api",
    "app",
    "awards",
    "django.contrib.postgres",
    "contacts",
    "corsheaders",
    "django_altcha",
    "oauth2_provider",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(conn_health_checks=True),
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Request exceptions go to the container's stderr so `docker logs` shows the
# traceback for a 500; Django's default only does this when DEBUG is on.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "app.AuthUser"

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "static-files"

MEDIA_ROOT = BASE_DIR / "uploads"

# Maximum accepted ADIF upload size (web form and API). The matcher parses
# the whole file into memory, so this cap bounds its memory use per upload.
MAX_LOG_FILE_SIZE = 100 * 1024 * 1024

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


ANYMAIL = {
    "MAILGUN_API_KEY": os.getenv("MAILGUN_API_KEY"),
    "MAILGUN_SENDER_DOMAIN": "radio.games",
}

EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

DEFAULT_FROM_EMAIL = "no-reply@radio.games"

SERVER_EMAIL = "no-reply@radio.games"

ALTCHA_HMAC_KEY = os.getenv("ALTCHA_HMAC_KEY", "")
ALTCHA_CACHE_ALIAS = "default"

OAUTH2_PROVIDER = {
    "SCOPES": {
        "read": "Read access to your matches and callsigns",
        "upload": "Upload ADIF logs on your behalf",
    },
    "DEFAULT_SCOPES": ["read"],
    "ACCESS_TOKEN_EXPIRE_SECONDS": 3600 * 24,  # 24 hours
    # "http" stays allowed for native-app loopback callbacks (RFC 8252):
    # desktop logging programs are the main OAuth consumers here
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https", "http"],
    # RFC 9700 (OAuth 2.0 Security BCP) compliance; these become the
    # django-oauth-toolkit 4.0 defaults
    "COMPLIANT_BCP_RFC9700_IMPLICIT_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PASSWORD_GRANT": True,
    "COMPLIANT_BCP_RFC9700_PKCE_METHOD": True,
    "COMPLIANT_BCP_RFC9700_ACCESS_TOKEN_TRANSPORT": True,
    "COMPLIANT_BCP_RFC9700_AUTHZ_RESPONSE_ISS": True,
    "COMPLIANT_BCP_RFC9700_TOKEN_STORAGE": True,
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
}

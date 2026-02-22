import os

from pathlib import Path

import dj_database_url

from env_tools import env_to_bool

BASE_DIR = Path(__file__).resolve().parent.parent

IS_PRODUCTION = os.getenv("ENV") == "production"

DEBUG = env_to_bool("DEBUG") and not IS_PRODUCTION

# if IS_PRODUCTION:
#     SECURE_HSTS_SECONDS = 3600

SECRET_KEY = os.getenv("SECRET_KEY")

SECURE_SSL_REDIRECT = IS_PRODUCTION

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

ALLOWED_HOSTS = ["*"]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

INSTALLED_APPS = [
    "anymail",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django_extensions",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "api",
    "app",
    "contacts",
    "corsheaders",
    "oauth2_provider",
    "rest_framework",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "app.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(conn_health_checks=True),
    "contacts": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "contacts.sqlite",
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=wal;",
            "timeout": 5,
        },
    },
}

DATABASE_ROUTERS = ["app.routers.MainRouter"]

# TODO_PRODUCTION: use Redis/kv
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "app.AuthUser"

AUTHENTICATION_BACKENDS = [
    "oauth2_provider.backends.OAuth2Backend",
    "django.contrib.auth.backends.ModelBackend",
]

OAUTH2_PROVIDER = {
    "SCOPES": {
        "read-contacts": "Read your contacts and matches",
        "write-contacts": "Upload contacts",
    }
}

REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ("oauth2_provider.contrib.rest_framework.OAuth2Authentication",)}

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

STATIC_ROOT = BASE_DIR / "static-files"

STORAGES = {
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

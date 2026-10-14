"""
Base settings shared by all environments. Environment-specific settings
(dev.py, prod.py) import * from here and override what they need.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-production")

DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Networks of the reverse proxy whose X-Real-Ip header is trusted as the
# visitor's IP (core.middleware.TrustedProxyClientIPMiddleware). Empty means
# REMOTE_ADDR is used as-is (dev). prod.py sets the Docker default.
TRUSTED_PROXY_CIDRS = env.list("TRUSTED_PROXY_CIDRS", default=[])

# Base URL of the platform, used to build absolute links (e.g. Telegram deep links).
SITE_URL = env("SITE_URL", default="http://127.0.0.1:8000")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "django_filters",
    "tenants",
    "accounts",
    "core",
    "landingpages",
    "leads",
    "telegram_integration",
    "meta_conversions",
    "google_forms_integration",
    "email_notifications",
]

MIDDLEWARE = [
    # Must be first: replaces REMOTE_ADDR with the visitor's real IP (from
    # the reverse proxy's X-Real-Ip) before anything reads it — ratelimit,
    # Lead.ip_address, Meta CAPI. See core/middleware.py.
    "core.middleware.TrustedProxyClientIPMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Resolves request.tenant from the Host header or leaves it None for the
    # path-based fallback. Must sit after SessionMiddleware (needs no session
    # data itself) and before anything that touches request.tenant.
    "tenants.middleware.TenantResolutionMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"

# Postgres when DATABASE_URL is set (beta: shared server, database
# agipages_beta); otherwise the SQLite file production still uses.
if env("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Manifest+compression only in prod.py — requires collectstatic to have run,
# which isn't true during local dev.
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Production serves /media/ from the host nginx (internal-static). The beta
# has no such route, so the app serves it itself until media moves to object
# storage (Cloudflare R2) before Phase 8.
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=False)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "landingpages:list"
LOGOUT_REDIRECT_URL = "accounts:login"

# Telegram bot integration (Milestone 6). Empty by default; set in .env.
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")

# SMTP for lead notification e-mails (email_notifications/). Empty
# EMAIL_HOST disables sending; set in .env (Mailcow da VPS em produção).
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")

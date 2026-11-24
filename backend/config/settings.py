"""Django settings for Hospital Care. Environment-specific values come from env vars (.env.example)."""

import os
import re
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from apps.matching.scoring import parse_scoring_config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


def positive_int_env(name, default):
    """A whole number of 1 or more from an environment variable. A bad value stops the server at startup."""
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a whole number of 1 or more, not {raw!r}.") from None
    if value < 1:
        raise ImproperlyConfigured(f"{name} must be a whole number of 1 or more, not {raw!r}.")
    return value


def non_negative_int_env(name, default):
    """A whole number of 0 or more from an environment variable. A bad value stops the server at startup."""
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a whole number of 0 or more, not {raw!r}.") from None
    if value < 0:
        raise ImproperlyConfigured(f"{name} must be a whole number of 0 or more, not {raw!r}.")
    return value


THROTTLE_RATE = re.compile(r"[1-9][0-9]*/[smhd][a-z]*")


def throttle_rate_env(name, default):
    """A rate such as 30/min or 30/hour, or empty to turn that limit off. A bad value stops the server."""
    raw = os.environ.get(name, default).strip()
    if raw == "":
        return None
    if not THROTTLE_RATE.fullmatch(raw):
        raise ImproperlyConfigured(
            f"{name} must be a rate such as 30/min or 30/hour, or empty to turn the limit off, not {raw!r}."
        )
    return raw


# Staging runs on Vercel (B14). Vercel sets VERCEL=1 while it builds and runs the app, and that changes a few
# defaults below (DEBUG off, its hosts, a shared cache, its proxy), so the project needs only
# DJANGO_SECRET_KEY and a database. Each default can still be overridden with its own variable.
ON_VERCEL = os.environ.get("VERCEL") == "1"

DEBUG = os.environ.get("DJANGO_DEBUG", "false" if ON_VERCEL else "true").lower() == "true"
# The development key is only for DEBUG. With DEBUG off the key must come from the environment (on Vercel, the
# project's DJANGO_SECRET_KEY), so a host that forgets it refuses to start, not sign sessions with a key from
# the code (F8).
DEV_SECRET_KEY = "dev-only-insecure-key-change-me"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or (DEV_SECRET_KEY if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ".vercel.app" if ON_VERCEL else "localhost,127.0.0.1")
# The Django admin at /admin/ (B13, F6). On under DEBUG; off otherwise unless DJANGO_ADMIN_ENABLED=true.
ADMIN_ENABLED = os.environ.get("DJANGO_ADMIN_ENABLED", "true" if DEBUG else "false").lower() == "true"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.accounts",
    "apps.hospitals",
    "apps.resources",
    "apps.blood",
    "apps.emergencies",
    "apps.matching",
    "apps.transfers",
    "apps.command_centre",
    "apps.pharmacy",
    "apps.equipment",
    "apps.operating_rooms",
    "apps.ambulances",
    "apps.specialists",
    "apps.staffing",
    "apps.metrics",
    "apps.notifications",
    "apps.audit",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Postgres via DATABASE_URL. SQLite fallback only so a fresh clone can run tests without Docker. A connection
# is kept between requests and checked before it's reused: on Vercel a copy of the app can sit idle long
# enough for the database to close it.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}
# On Vercel the database (Neon) is reached through its connection pooler, which hands each transaction to
# whichever server connection is free, so a database cursor can't outlive its transaction. Large results are
# then read the ordinary way (the audit export is the one place that streams them, and it's capped).
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = ON_VERCEL

# Sign-in limits (B13, F4) and the lockout after failed passwords count attempts in the cache. Vercel runs
# several copies of the app at once, so there the count is kept in the database, where every copy sees it. One
# server (local, Docker) can keep it in memory. `manage.py createcachetable` makes the table; the Vercel build
# runs it.
if os.environ.get("DJANGO_CACHE", "database" if ON_VERCEL else "memory") == "database":
    CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

# Sign out after inactivity (story 1.1): every request pushes the expiry back, so only idle sessions end.
SESSION_COOKIE_AGE = int(os.environ.get("SESSION_IDLE_MINUTES", "30")) * 60
SESSION_SAVE_EVERY_REQUEST = True

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:5173")

# Session auth. On Vercel the site and the API share one domain; the SameSite=None cookies date from the login
# story's two-domain plan and still work. Locally (DEBUG) both run on localhost, over plain http with Lax
# cookies.
if not DEBUG:
    SESSION_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # HTTPS only (B13). A host's health check may reach the app over plain HTTP, so that one path is exempt.
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]
    # How long browsers keep to HTTPS for this host: 3600 for the first deploy, then 31536000 (one year) once
    # staging has been HTTPS-only for a week, because browsers cache it. Preload stays off (B13 non-goal).
    SECURE_HSTS_SECONDS = positive_int_env("DJANGO_HSTS_SECONDS", 3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # deploy check W005; this host's own subdomains only
    # W021 asks for the HSTS preload token, a commitment to the browser preload list. That is out of scope for
    # B13, so the header leaves the token out and the check is silenced on purpose.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Blood bank rules (Sprint 3). Each can be overridden with an environment variable.
BLOOD_NEAR_EXPIRY_DAYS = int(os.environ.get("BLOOD_NEAR_EXPIRY_DAYS", "3"))  # story #19
BLOOD_LOW_STOCK_UNITS = int(os.environ.get("BLOOD_LOW_STOCK_UNITS", "5"))  # per group and component
BLOOD_MIN_DONATION_INTERVAL_DAYS = int(os.environ.get("BLOOD_MIN_DONATION_INTERVAL_DAYS", "56"))  # story #21
BLOOD_APPOINTMENT_SLOT_MINUTES = int(os.environ.get("BLOOD_APPOINTMENT_SLOT_MINUTES", "30"))  # story #22

# A critical case still unfulfilled after this many minutes in its current status is escalated (story #35).
EMERGENCY_ESCALATION_MINUTES = positive_int_env("EMERGENCY_ESCALATION_MINUTES", 30)

# A reserved resource is held for this many minutes unless it is used or released first (story #43). The
# hold's end is stored when it is made, so changing this later doesn't move holds already made.
RESERVATION_HOLD_MINUTES = positive_int_env("RESERVATION_HOLD_MINUTES", 30)

# Candidate scoring (story #40). MATCHING_SCORING is JSON per resource type: the strategy and the factor
# weights, merged over the defaults in apps/matching/scoring.py. A bad value stops the server at startup.
MATCHING_SCORING = parse_scoring_config(os.environ.get("MATCHING_SCORING", ""))
# The distance at which the distance factor reaches 0.
MATCHING_MAX_DISTANCE_KM = positive_int_env("MATCHING_MAX_DISTANCE_KM", 50)

# Sign-in and sign-up limits per client address (B13, F4). A rate is "<count>/<period>" (second, minute,
# hour or day). Empty turns that limit off. The defaults are generous: hospital computers share an address.
AUTH_THROTTLE_RATES = {
    "auth_login": throttle_rate_env("DJANGO_LOGIN_THROTTLE", "30/min"),
    "auth_signup": throttle_rate_env("DJANGO_SIGNUP_THROTTLE", "30/hour"),
}
# How many reverse proxies sit in front of the app, each appending to X-Forwarded-For (B13, F4). On Vercel its
# edge is the one proxy (1), and it writes the client's address there itself. 0 (local development) means
# none: REMOTE_ADDR is the client's address.
TRUSTED_PROXY_COUNT = non_negative_int_env("DJANGO_TRUSTED_PROXY_COUNT", 1 if ON_VERCEL else 0)

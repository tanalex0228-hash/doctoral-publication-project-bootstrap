import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def required_environment(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"{name} must be configured through the environment.")
    return value


def environment_flag(name, *, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean environment value.")


def environment_integer(name, *, default=0, minimum=0):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise ImproperlyConfigured(f"{name} must be an integer environment value.") from error
    if parsed < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return parsed


def environment_csv(name, *, required=False):
    values = [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]
    if required and not values:
        raise ImproperlyConfigured(f"{name} must contain at least one value.")
    return values


DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").lower()
if DJANGO_ENV not in {"development", "staging", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV must be development, staging, or production.")

SECRET_KEY = required_environment("DJANGO_SECRET_KEY")
DEBUG = environment_flag("DJANGO_DEBUG", default=False)
if DJANGO_ENV == "production" and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")
ALLOWED_HOSTS = environment_csv("DJANGO_ALLOWED_HOSTS", required=True)
CSRF_TRUSTED_ORIGINS = environment_csv("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles",
    "accounts", "audit", "taxonomy", "doctoral_students", "professors", "advising",
    "publications", "documents", "review", "reporting", "dashboard", "public_site",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# PostgreSQL is mandatory in every environment, including local development and tests.
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": required_environment("POSTGRES_DB"),
    "USER": required_environment("POSTGRES_USER"),
    "PASSWORD": required_environment("POSTGRES_PASSWORD"),
    "HOST": required_environment("POSTGRES_HOST"),
    "PORT": required_environment("POSTGRES_PORT"),
    "OPTIONS": {"connect_timeout": environment_integer("POSTGRES_CONNECT_TIMEOUT", default=5, minimum=1)},
    "TEST": {"NAME": os.environ.get("POSTGRES_TEST_DB", f"test_{required_environment('POSTGRES_DB')}")},
}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "zh-hant"
TIME_ZONE = "Asia/Taipei"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT", BASE_DIR / "staticfiles"))
# No MEDIA_URL: evidence files are private and served only by permission-checked views.
MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT", BASE_DIR / "private_media"))
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:student"

# TLS is terminated by the deployment proxy. These options stay opt-in for
# local HTTP development but are mandatory once DJANGO_ENV=production.
SECURE_SSL_REDIRECT = environment_flag("DJANGO_SECURE_SSL_REDIRECT", default=False)
SESSION_COOKIE_SECURE = environment_flag("DJANGO_SESSION_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = environment_flag("DJANGO_CSRF_COOKIE_SECURE", default=SECURE_SSL_REDIRECT)
if environment_flag("DJANGO_TRUST_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = environment_integer("DJANGO_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = environment_flag("DJANGO_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = environment_flag("DJANGO_HSTS_PRELOAD", default=False)
if SECURE_HSTS_PRELOAD and (
    SECURE_HSTS_SECONDS < 31_536_000 or not SECURE_HSTS_INCLUDE_SUBDOMAINS
):
    raise ImproperlyConfigured(
        "HSTS preload requires at least one year and include_subdomains."
    )
if DJANGO_ENV == "production" and not (
    SECURE_SSL_REDIRECT and SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE
):
    raise ImproperlyConfigured(
        "Production requires HTTPS redirect plus secure session and CSRF cookies."
    )

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "documents.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

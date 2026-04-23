"""Minimal Django settings for the RBAC experiment.

SQLite by default — the RBAC patterns (closure table, custom backend,
just-in-time expiry, object-level scope via GenericForeignKey) all work on any
DB. authentik's production design uses a PostgreSQL materialized view plus
`pgtrigger` for the closure refresh; we use a plain model + post_save signal
here for readability and zero infra.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-for-production"  # noqa: S105
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rbac",
    "library",
]

MIDDLEWARE = []
ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

# The two-backend pattern from the talk:
#   1. ModelBackendNoAuthz — inherits Django authentication, returns empty/False from every authz method
#   2. RBACBackend         — single source of truth for has_perm, backed by our RBAC tables
AUTHENTICATION_BACKENDS = [
    "rbac.backends.ModelBackendNoAuthz",
    "rbac.backends.RBACBackend",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

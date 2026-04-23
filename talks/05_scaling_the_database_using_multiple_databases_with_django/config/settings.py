"""
Settings for the multi-DB demo.

Two SQLite files simulate a primary + replica setup. The router (either the
naive one or the smart one, toggled by the ``ROUTER`` env var) decides which
alias serves each query. A ``sync_replica`` management command copies the
primary file onto the replica file to simulate replication catching up.

For tests, ``TEST.MIRROR`` points the replica alias at the primary's test DB
so only one test database is actually created — this is the recommended
pattern in Django's docs.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-for-production"  # noqa: S105 — demo project
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",   # required for GenericForeignKey demo
    "django.contrib.auth",
    "scaling",
]

MIDDLEWARE = []

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "primary.sqlite3",
        "TEST": {"NAME": BASE_DIR / "test.sqlite3"},
    },
    "replica": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "replica.sqlite3",
        # Point the test replica at the primary's test DB so only one test
        # database is created. Requires TransactionTestCase (not TestCase).
        "TEST": {"MIRROR": "default"},
    },
}

# Switch routers with: ROUTER=naive python manage.py ...
# "smart" (default) applies all three fixes from the talk.
# "naive" shows the bugs — useful for the demo commands.
_ROUTER_MODE = os.environ.get("ROUTER", "smart").lower()

DATABASE_ROUTERS = {
    "smart": ["scaling.routers.PrimaryReplicaRouter"],
    "naive": ["scaling.routers.NaiveRouter"],
}[_ROUTER_MODE]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

"""
Settings for the caving-incidents pipeline demo.

Connection defaults match the bundled docker-compose.yml (Postgres on
localhost:55433). Override with DB_HOST/DB_PORT etc. if you want to point
at something else.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-for-production"  # noqa: S105 — demo project
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "treebeard",       # django-treebeard for the Location MP_Node tree
    "incidents",
]

MIDDLEWARE = []

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "incidents"),
        "USER": os.environ.get("DB_USER", "incidents"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "incidents"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "55433"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

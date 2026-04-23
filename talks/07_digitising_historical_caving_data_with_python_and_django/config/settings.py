"""
Settings for the caving-incidents pipeline demo.

Single Postgres database. Connection defaults match the bundled
docker-compose.yml (port 55433 on localhost). Override with env vars
if you want to point at something else.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-for-production"  # noqa: S105 -- demo project
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
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "caving"),
        "USER": os.environ.get("DB_USER", "caving"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "caving"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "55433"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

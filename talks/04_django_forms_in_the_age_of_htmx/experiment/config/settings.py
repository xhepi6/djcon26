"""
Minimal Django settings for the single-field-form demo.

Two things worth noticing:

1. `'django.forms'` is in INSTALLED_APPS. This activates the app-template
   loader for form rendering so our `templates/django/forms/dl.html` and
   `templates/django/forms/field.html` overrides are picked up project-wide.

2. FORM_RENDERER is set to TemplatesSetting so Django looks for widget
   templates in your normal TEMPLATES.DIRS (not only inside django/forms).
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-only-not-for-production"  # noqa: S105 — demo project
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.forms",              # required for app-dir form template overrides
    "books",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

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

# Look for widget templates in TEMPLATES.DIRS as well as django/forms/templates.
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True

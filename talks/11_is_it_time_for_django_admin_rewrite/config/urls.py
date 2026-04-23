from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

from djadmin import site

from test_views import state_view, check_view, reset_view


def home(_request):
    return HttpResponse(
        "<pre>Talk 11 — Is It Time for a Django Admin Rewrite?\n\n"
        "Routes:\n"
        "  /admin/    stock Django admin (for comparison)\n"
        "  /djadmin/  admin-deux (the new admin)\n"
        "  /test/     interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_data\n"
        "  python manage.py createsuperuser\n"
        "  python manage.py djadmin_inspect\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    # Stock Django admin — for comparison
    path("admin/", admin.site.urls),
    # Django-Admin-Deux — the new admin
    path("djadmin/", include(site.urls)),
    # Auth views (login/logout)
    path("accounts/", include("django.contrib.auth.urls")),
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/check/", check_view, name="test-check"),
    path("test/api/reset/", reset_view, name="test-reset"),
]

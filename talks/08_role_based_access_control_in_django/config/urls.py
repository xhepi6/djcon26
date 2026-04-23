from django.http import HttpResponse
from django.urls import path
from django.views.generic import TemplateView

from test_views import (
    check_view,
    expire_view,
    reset_view,
    state_view,
)


def home(_request):
    return HttpResponse(
        "<pre>Talk 08 — Role-Based Access Control in Django\n\n"
        "Routes:\n"
        "  /test/   interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_data\n"
        "  python manage.py show_rbac\n"
        "  python manage.py demo_checks\n"
        "  python manage.py check_perm alice library.change_book\n"
        "  python manage.py check_perm bob library.change_book --book Dune\n"
        "  python manage.py check_perm alice library.view_book --sql\n"
        "  python manage.py demo_jit\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/check/", check_view, name="test-check"),
    path("test/api/reset/", reset_view, name="test-reset"),
    path("test/api/expire/", expire_view, name="test-expire"),
]

from django.http import HttpResponse
from django.urls import path
from django.views.generic import TemplateView

from test_views import (
    audit_view,
    check_view,
    hashes_view,
    state_view,
)


def home(_request):
    return HttpResponse(
        "<pre>Talk 10 — What's in Your Dependencies?\n\n"
        "Routes:\n"
        "  /test/   interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py audit_deps\n"
        "  python manage.py check_dep &lt;package&gt;\n"
        "  python manage.py show_hashes\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/audit/", audit_view, name="test-audit"),
    path("test/api/check/", check_view, name="test-check"),
    path("test/api/hashes/", hashes_view, name="test-hashes"),
]

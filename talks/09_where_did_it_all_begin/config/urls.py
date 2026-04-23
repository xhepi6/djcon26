from django.http import HttpResponse
from django.urls import path
from django.views.generic import TemplateView

from test_views import (
    demo_atomic_view,
    demo_subatomic_view,
    seed_view,
    state_view,
    transfer_view,
)


def home(_request):
    return HttpResponse(
        "<pre>Talk 09 — Where Did It All Begin? (django-subatomic)\n\n"
        "Routes:\n"
        "  /test/   interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_data\n"
        "  python manage.py demo_atomic\n"
        "  python manage.py demo_subatomic\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/demo-atomic/", demo_atomic_view, name="test-demo-atomic"),
    path("test/api/demo-subatomic/", demo_subatomic_view, name="test-demo-subatomic"),
    path("test/api/seed/", seed_view, name="test-seed"),
    path("test/api/transfer/", transfer_view, name="test-transfer"),
]

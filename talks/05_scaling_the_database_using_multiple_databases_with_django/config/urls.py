from django.urls import path
from django.http import HttpResponse
from django.views.generic import TemplateView

from test_views import (
    demo_atomic_view,
    demo_gfk_view,
    demo_get_or_create_view,
    demo_lag_view,
    reset_view,
    seed_view,
    state_view,
    sync_view,
)


def home(_request):
    return HttpResponse(
        "<pre>Multi-DB scaling demo (Talk 05).\n\n"
        "Routes:\n"
        "  /         this page\n"
        "  /test/    interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_data\n"
        "  python manage.py demo_lag\n"
        "  python manage.py demo_atomic\n"
        "  python manage.py demo_get_or_create\n"
        "  python manage.py demo_gfk_bug\n"
        "  python manage.py sync_replica\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/sync/", sync_view, name="test-sync"),
    path("test/api/seed/", seed_view, name="test-seed"),
    path("test/api/reset/", reset_view, name="test-reset"),
    path("test/api/demo-lag/", demo_lag_view, name="test-demo-lag"),
    path("test/api/demo-atomic/", demo_atomic_view, name="test-demo-atomic"),
    path("test/api/demo-get-or-create/", demo_get_or_create_view, name="test-demo-get-or-create"),
    path("test/api/demo-gfk/", demo_gfk_view, name="test-demo-gfk"),
]

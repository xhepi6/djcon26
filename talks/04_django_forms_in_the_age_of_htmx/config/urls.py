from django.urls import include, path
from django.views.generic import TemplateView

from test_views import registry_view, reset_view, state_view

urlpatterns = [
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/registry/", registry_view, name="test-registry"),
    path("test/api/reset/", reset_view, name="test-reset"),
    # Book app
    path("", include("books.urls")),
]

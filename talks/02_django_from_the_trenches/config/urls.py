from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from shortener.test_views import explain_view
from shortener.views import (
    find_by_date_range_view,
    find_by_domain_view,
    find_by_url_view,
    find_unused_view,
    resolve_url,
)

# --- App endpoints (the actual URL shortener) ---
urlpatterns = [
    path("admin/", admin.site.urls),
    path("r/<str:key>/", resolve_url, name="resolve"),
    path("by-domain/<str:domain>/", find_by_domain_view, name="by-domain"),
    path("unused/", find_unused_view, name="unused"),
    path("by-url/", find_by_url_view, name="by-url"),
    path("by-date/", find_by_date_range_view, name="by-date"),

    # --- Test panel (EXPLAIN ANALYZE for each index type) ---
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("explain/", explain_view, name="explain"),
]

from django.contrib import admin
from django.urls import path

from shortener.views import resolve_url, find_by_domain_view, find_unused_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("r/<str:key>/", resolve_url, name="resolve"),
    path("by-domain/<str:domain>/", find_by_domain_view, name="by-domain"),
    path("unused/", find_unused_view, name="unused"),
]

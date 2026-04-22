from django.contrib import admin
from django.urls import include, path

from djadmin import site

urlpatterns = [
    # Stock Django admin — for comparison
    path("admin/", admin.site.urls),
    # Django-Admin-Deux — the new admin
    path("djadmin/", include(site.urls)),
    # Auth views (login/logout)
    path("accounts/", include("django.contrib.auth.urls")),
]

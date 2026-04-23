from django.urls import path
from django.http import HttpResponse
from django.views.generic import TemplateView

from test_views import partitions_view, pruning_view, orm_view, seed_view


def home(_request):
    return HttpResponse(
        "<pre>Partitioning demo — Talk 06: Partitioning Very Large Tables\n\n"
        "Routes:\n"
        "  /           this page\n"
        "  /test/      interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_data\n"
        "  python manage.py show_partitions\n"
        "  python manage.py demo_pruning\n"
        "  python manage.py demo_pruning --no-partition-key\n"
        "  python manage.py demo_orm\n"
        "  python manage.py add_partition 2026-06\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/partitions/", partitions_view, name="test-partitions"),
    path("test/api/pruning/", pruning_view, name="test-pruning"),
    path("test/api/orm/", orm_view, name="test-orm"),
    path("test/api/seed/", seed_view, name="test-seed"),
]

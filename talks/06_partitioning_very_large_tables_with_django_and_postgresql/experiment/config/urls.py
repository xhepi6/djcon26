from django.urls import path
from django.http import HttpResponse


def home(_request):
    return HttpResponse(
        "<pre>Partitioning demo. See README.md. Try:\n"
        "  python manage.py seed_data\n"
        "  python manage.py show_partitions\n"
        "  python manage.py demo_pruning\n"
        "  python manage.py demo_pruning --no-partition-key\n"
        "  python manage.py demo_orm\n"
        "  python manage.py add_partition 2026-06\n"
        "</pre>"
    )


urlpatterns = [path("", home)]

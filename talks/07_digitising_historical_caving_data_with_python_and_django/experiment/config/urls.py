from django.urls import path
from django.http import HttpResponse


def home(_request):
    return HttpResponse(
        "<pre>Caving incidents pipeline demo. See README.md. Try:\n"
        "  python manage.py seed_raw\n"
        "  python manage.py process\n"
        "  python manage.py show_pipeline\n"
        "  python manage.py demo_fuzzy_date\n"
        "  python manage.py demo_tree\n"
        "</pre>"
    )


urlpatterns = [path("", home)]

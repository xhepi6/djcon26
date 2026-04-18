from django.urls import path
from django.http import HttpResponse


def home(_request):
    return HttpResponse(
        "<pre>Multi-DB demo. See README.md. Try:\n"
        "  python manage.py demo_lag\n"
        "  python manage.py demo_atomic\n"
        "  python manage.py demo_get_or_create\n"
        "  python manage.py demo_gfk_bug\n"
        "  python manage.py test scaling\n"
        "</pre>"
    )


urlpatterns = [path("", home)]

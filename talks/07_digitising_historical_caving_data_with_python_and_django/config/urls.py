from django.urls import path
from django.http import HttpResponse
from django.views.generic import TemplateView

from test_views import (
    state_view,
    fuzzy_date_demo_view,
    reset_and_seed_view,
    run_pipeline_view,
    rerun_pipeline_view,
    tree_query_view,
)


def home(_request):
    return HttpResponse(
        "<pre>Caving incidents pipeline demo.\n\n"
        "Routes:\n"
        "  /test/      interactive test panel\n\n"
        "Management commands:\n"
        "  python manage.py seed_raw\n"
        "  python manage.py process\n"
        "  python manage.py show_pipeline\n"
        "  python manage.py demo_fuzzy_date\n"
        "  python manage.py demo_tree\n"
        "</pre>"
    )


urlpatterns = [
    path("", home),
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/fuzzy-dates/", fuzzy_date_demo_view, name="test-fuzzy-dates"),
    path("test/api/reset-seed/", reset_and_seed_view, name="test-reset-seed"),
    path("test/api/run-pipeline/", run_pipeline_view, name="test-run-pipeline"),
    path("test/api/rerun-pipeline/", rerun_pipeline_view, name="test-rerun-pipeline"),
    path("test/api/tree-query/", tree_query_view, name="test-tree-query"),
]

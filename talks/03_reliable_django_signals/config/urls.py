from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from test_views import (
    create_order_view,
    naive_crash_view,
    naive_gap_view,
    poll_orders_view,
    process_tasks_view,
    reliable_send_view,
    reset_view,
    state_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Test panel
    path("test/", TemplateView.as_view(template_name="test.html"), name="test-panel"),
    path("test/api/state/", state_view, name="test-state"),
    path("test/api/create-order/", create_order_view, name="test-create-order"),
    path("test/api/naive-crash/", naive_crash_view, name="test-naive-crash"),
    path("test/api/naive-gap/", naive_gap_view, name="test-naive-gap"),
    path("test/api/reliable-send/", reliable_send_view, name="test-reliable-send"),
    path("test/api/process-tasks/", process_tasks_view, name="test-process-tasks"),
    path("test/api/poll/", poll_orders_view, name="test-poll"),
    path("test/api/reset/", reset_view, name="test-reset"),
]

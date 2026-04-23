from django.urls import path

from . import views

urlpatterns = [
    path("", views.BookListView.as_view(), name="book-list"),
    # Classic one-big-form flow — for comparison
    path("new/", views.BookCreateView.as_view(), name="book-new"),
    path("<int:pk>/edit/", views.BookUpdateView.as_view(), name="book-edit"),
    # Single-field flow — all three endpoints share the ``fieldname`` URL kwarg
    path(
        "<int:pk>/<str:fieldname>/",
        views.book_field_form,
        name="book-field-form",
    ),
    path(
        "<int:pk>/<str:fieldname>/display/",
        views.book_field_display,
        name="book-field-display",
    ),
    path(
        "<int:pk>/<str:fieldname>/update/",
        views.book_field_update,
        name="book-field-update",
    ),
]

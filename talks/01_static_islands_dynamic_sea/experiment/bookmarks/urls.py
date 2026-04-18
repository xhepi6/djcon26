from django.urls import path

from . import views

urlpatterns = [
    path("bookmarks/", views.BookmarkList.as_view(), name="bookmark-list"),
    path("bookmarks/<int:pk>/", views.BookmarkDetail.as_view(), name="bookmark-detail"),
    path("bookmarks/nested/", views.bookmark_list_nested, name="bookmark-nested"),
    path("bookmarks/flat/", views.bookmark_list_flat, name="bookmark-flat"),
]

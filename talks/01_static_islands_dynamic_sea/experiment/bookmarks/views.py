"""
Views showing different ways to use Mantle.

Run the server and try:
  GET  /api/bookmarks/          — list (DRF + Mantle shape)
  POST /api/bookmarks/          — create
  GET  /api/bookmarks/<id>/     — detail
  GET  /api/bookmarks/nested/   — list with nested user data
  GET  /api/bookmarks/flat/     — list with flattened username
  GET  /api/docs/               — Swagger UI
"""

import attrs
from django.http import JsonResponse
from mantle import Query, compose_validators, create, unique_field
from mantle_drf.generics import ListCreateAPIView, RetrieveAPIView

from .models import Bookmark
from .shapes import BookmarkData, BookmarkFlat, BookmarkShape, BookmarkWithUser


# --- DRF views using mantle shapes (replaces serializers) ---

class BookmarkList(ListCreateAPIView):
    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape


class BookmarkDetail(RetrieveAPIView):
    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape


# --- Plain Django views using Mantle Query directly ---

def bookmark_list_nested(request):
    """Fetches bookmarks with nested user data. No N+1."""
    bookmarks = Query(Bookmark.objects.all(), BookmarkWithUser).all()
    data = [attrs.asdict(b) for b in bookmarks]
    return JsonResponse(data, safe=False)


def bookmark_list_flat(request):
    """Fetches bookmarks with username flattened via @overrides."""
    bookmarks = Query(Bookmark.objects.all(), BookmarkFlat).all()
    data = [attrs.asdict(b) for b in bookmarks]
    return JsonResponse(data, safe=False)


# --- Example: create with validation ---

bookmark_validator = compose_validators(
    unique_field("url"),
)


def create_bookmark_example():
    """Not a view — just shows how create + validation works."""
    new = create(
        Bookmark,
        BookmarkData(
            url="https://noumenal.es",
            title="Mantle docs",
            comment="Check this out",
            favourite=True,
        ),
        validator=bookmark_validator,
    )
    return new

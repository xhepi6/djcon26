"""
Views showing different ways to use Mantle.

DRF endpoints appear in Swagger UI at /api/docs/.
Plain Django views are testable at /test/.
"""

import json

import attrs
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mantle import Query, compose_validators, create, unique_field, update
from mantle_drf.generics import ListCreateAPIView, RetrieveAPIView

from .models import Bookmark
from .shapes import (
    BookmarkData,
    BookmarkFlat,
    BookmarkShape,
    BookmarkWithUser,
    BookmarkWriteData,
)


# --- DRF views using Mantle shapes (replaces serializers) ---

class BookmarkList(ListCreateAPIView):
    """List all bookmarks or create one. Uses Mantle shape instead of a serializer."""

    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape

    def perform_create(self, shape):
        data = attrs.asdict(shape)
        return Bookmark.objects.create(**data, user=User.objects.first())


class BookmarkDetail(RetrieveAPIView):
    """Retrieve a single bookmark by ID."""

    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape


# --- Plain Django views using Mantle Query ---

def bookmark_list_nested(request):
    """Nested user data. Mantle auto-generates prefetch — no N+1."""
    bookmarks = Query(Bookmark.objects.all(), BookmarkWithUser).all()
    return JsonResponse([attrs.asdict(b) for b in bookmarks], safe=False)


def bookmark_list_flat(request):
    """Flattened username via @overrides — single JOIN query."""
    bookmarks = Query(Bookmark.objects.all(), BookmarkFlat).all()
    return JsonResponse([attrs.asdict(b) for b in bookmarks], safe=False)


def bookmark_list_naive(request):
    """Same data as /nested/ but with N+1. Shows what Mantle prevents."""
    from django.db import connection

    start = len(connection.queries)
    data = []
    for b in Bookmark.objects.all():
        data.append({
            "url": b.url,
            "title": b.title,
            "comment": b.comment,
            "favourite": b.favourite,
            "user": {"username": b.user.username},
        })
    query_count = len(connection.queries) - start

    return JsonResponse({
        "bookmarks": data,
        "debug": {
            "queries_executed": query_count,
            "warning": "N+1! Compare with /api/bookmarks/nested/",
        },
    })


# --- Validated create/update using Mantle's create() and update() ---

bookmark_validator = compose_validators(
    unique_field("url"),
)


@csrf_exempt
def bookmark_create_validated(request):
    """Create with Mantle validation (rejects duplicate URLs)."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    body = json.loads(request.body)
    user = User.objects.first()

    shape = BookmarkWriteData(
        url=body["url"],
        title=body.get("title", ""),
        comment=body.get("comment", ""),
        favourite=body.get("favourite", False),
        user_id=user.pk,
    )

    try:
        obj = create(Bookmark, shape, validator=bookmark_validator)
        return JsonResponse({
            "created": {"id": obj.pk, "url": obj.url, "title": obj.title},
        }, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@csrf_exempt
def bookmark_update_validated(request, pk):
    """Update with Mantle validation. Only touches shape fields (not user)."""
    if request.method != "PUT":
        return JsonResponse({"error": "PUT only"}, status=405)

    body = json.loads(request.body)
    bookmark = Bookmark.objects.get(pk=pk)

    shape = BookmarkData(
        url=body["url"],
        title=body.get("title", bookmark.title),
        comment=body.get("comment", bookmark.comment),
        favourite=body.get("favourite", bookmark.favourite),
    )

    try:
        updated = update(bookmark, shape, validator=bookmark_validator)
        return JsonResponse({
            "updated": {"id": updated.pk, "url": updated.url, "title": updated.title},
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

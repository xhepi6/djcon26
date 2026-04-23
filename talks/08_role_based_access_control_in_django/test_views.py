"""
Test panel API for Talk 08: Role-Based Access Control in Django.

Endpoints power the interactive /test/ page. Kept out of the rbac/ and
library/ apps so those stay clean copies of what the talk describes.
"""

from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection, reset_queries
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from library.models import Book
from rbac.models import Role, RoleAncestry, UserRole

User = get_user_model()


# ---- canonical matrix -------------------------------------------------------
# Same rows as rbac/management/commands/demo_checks.py — keep in sync.
CASES = [
    ("alice", "library.view_book",    None,       True,  "editor → viewer (closure)"),
    ("alice", "library.change_book",  None,       True,  "editor"),
    ("alice", "library.delete_book",  None,       False, "no librarian"),
    ("bob",   "library.view_book",    None,       True,  "viewer (global)"),
    ("bob",   "library.change_book",  None,       False, "no global editor"),
    ("bob",   "library.change_book",  "Dune",     True,  "editor scoped to Dune"),
    ("bob",   "library.change_book",  "Hyperion", False, "scope mismatch"),
    ("carol", "library.add_book",     None,       True,  "librarian (if unexpired)"),
    ("carol", "library.delete_book",  None,       True,  "librarian (if unexpired)"),
    ("dave",  "library.archive_book", None,       True,  "archiver — custom perm"),
    ("dave",  "library.view_book",    None,       False, "archiver is a separate root"),
    ("admin", "library.archive_book", None,       True,  "is_superuser short-circuit"),
]


def state_view(request):
    """Everything the /test/ page needs to render in one shot."""
    # Role tree (roots + recursive children)
    tree = [_role_node(r) for r in Role.objects.filter(parent__isnull=True).order_by("name")]

    # Closure rows — ordered for readability
    closure = [
        {"ancestor": r.ancestor.name, "descendant": r.descendant.name, "depth": r.depth}
        for r in RoleAncestry.objects
            .select_related("ancestor", "descendant")
            .order_by("descendant__name", "depth", "ancestor__name")
    ]

    # Users & assignments (with expiry countdown for JIT visualisation)
    now = timezone.now()
    users = []
    for u in User.objects.order_by("username"):
        assignments = []
        for a in UserRole.objects.filter(user=u).select_related("role", "content_type"):
            assignments.append({
                "role": a.role.name,
                "scope": str(a.scope) if a.content_type_id else None,
                "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                "seconds_left": (
                    int((a.expires_at - now).total_seconds())
                    if a.expires_at is not None else None
                ),
                "expired": (
                    a.expires_at is not None and a.expires_at <= now
                ),
            })
        users.append({
            "username": u.username,
            "is_superuser": u.is_superuser,
            "assignments": assignments,
        })

    books = list(Book.objects.order_by("title").values("id", "title"))

    # Canonical matrix — re-run live so results reflect current state
    matrix = []
    for username, perm, title, expected, why in CASES:
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue
        obj = Book.objects.filter(title=title).first() if title else None
        actual = user.has_perm(perm, obj) if obj else user.has_perm(perm)
        matrix.append({
            "username": username,
            "perm": perm,
            "object": title or "—",
            "expected": expected,
            "actual": actual,
            "match": actual is expected,
            "why": why,
        })

    # Permissions with a role attached — the vocabulary the whole demo uses
    perms = []
    ct_ids = [ContentType.objects.get_for_model(Book).id]
    for p in Permission.objects.filter(content_type_id__in=ct_ids).select_related("content_type"):
        perms.append({
            "codename": p.codename,
            "app_label": p.content_type.app_label,
            "full": f"{p.content_type.app_label}.{p.codename}",
            "name": p.name,
        })

    return JsonResponse({
        "tree": tree,
        "closure": closure,
        "users": users,
        "books": books,
        "permissions": perms,
        "matrix": matrix,
        "now": now.isoformat(),
    })


def _role_node(role: Role) -> dict:
    return {
        "name": role.name,
        "permissions": sorted(
            f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.all()
        ),
        "children": [_role_node(c) for c in role.children.order_by("name")],
    }


@csrf_exempt
@require_POST
def check_view(request):
    """Run user.has_perm(perm[, book]) and return {result, sql}.

    `sql` is the list of SQL statements Django actually executed — the
    talk's headline point is that a correctly-designed RBAC reduces a
    permission check to a single JOIN query.
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    username = payload.get("username")
    perm = payload.get("perm")
    book_title = payload.get("book")

    if not username or not perm:
        return JsonResponse({"ok": False, "error": "username and perm required"}, status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({"ok": False, "error": f"no such user: {username}"}, status=404)

    obj = None
    if book_title:
        obj = Book.objects.filter(title=book_title).first()
        if obj is None:
            return JsonResponse({"ok": False, "error": f"no such book: {book_title}"}, status=404)

    # Capture every SQL statement the has_perm() call runs.
    reset_queries()
    connection.force_debug_cursor = True
    try:
        result = user.has_perm(perm, obj) if obj else user.has_perm(perm)
    finally:
        connection.force_debug_cursor = False

    return JsonResponse({
        "ok": True,
        "username": username,
        "perm": perm,
        "book": book_title,
        "result": bool(result),
        "sql": [q["sql"] for q in connection.queries],
        "query_count": len(connection.queries),
    })


@csrf_exempt
@require_POST
def reset_view(request):
    """Re-seed everything and give carol a 60s window for the panel.

    `seed_data` (CLI) gives carol 10s — right for `demo_jit`. That's too
    short for someone reading the page, so we extend it here.
    """
    call_command("seed_data")
    carol_role = (
        UserRole.objects
        .filter(user__username="carol", role__name="librarian")
        .first()
    )
    if carol_role is not None:
        carol_role.expires_at = timezone.now() + timezone.timedelta(seconds=60)
        carol_role.save()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def expire_view(request):
    """Set carol's librarian assignment to expire in N seconds (default 5)."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    seconds = int(payload.get("seconds", 5))
    carol = User.objects.filter(username="carol").first()
    if carol is None:
        return JsonResponse({"ok": False, "error": "carol not found — seed first"}, status=404)

    assignment = UserRole.objects.filter(user=carol, role__name="librarian").first()
    if assignment is None:
        return JsonResponse({"ok": False, "error": "no librarian assignment for carol"}, status=404)

    assignment.expires_at = timezone.now() + timezone.timedelta(seconds=seconds)
    assignment.save()
    return JsonResponse({
        "ok": True,
        "expires_at": assignment.expires_at.isoformat(),
        "seconds": seconds,
    })

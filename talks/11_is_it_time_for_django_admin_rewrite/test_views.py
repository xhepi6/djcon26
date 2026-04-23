"""
Test panel API for Talk 11: Is It Time for a Django Admin Rewrite?

Endpoints power the interactive /test/ page. Kept out of the catalog/ app
so it stays a clean copy of what the talk describes.
"""

from __future__ import annotations

import io
import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import Author, Category, Product

User = get_user_model()


def state_view(request):
    """Everything the /test/ page needs to render in one shot."""
    categories = list(
        Category.objects.order_by("name").values("id", "name", "slug")
    )
    authors = list(
        Author.objects.order_by("last_name", "first_name").values(
            "id", "first_name", "last_name", "email"
        )
    )
    products = []
    for p in Product.objects.select_related("category", "author").order_by("name"):
        products.append({
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "category": p.category.name,
            "author": str(p.author) if p.author else None,
            "price": str(p.price),
            "status": p.status,
        })

    # Run djadmin_inspect and capture its output
    buf = io.StringIO()
    try:
        call_command("djadmin_inspect", stdout=buf)
        inspect_output = buf.getvalue()
    except Exception as exc:
        inspect_output = f"Error: {exc}"

    has_superuser = User.objects.filter(is_superuser=True).exists()

    return JsonResponse({
        "categories": categories,
        "authors": authors,
        "products": products,
        "inspect_output": inspect_output,
        "has_superuser": has_superuser,
        "admin_url": "/admin/",
        "djadmin_url": "/djadmin/",
    })


@csrf_exempt
@require_POST
def check_view(request):
    """Compare what's registered in stock admin vs admin-deux."""
    from django.contrib.admin.sites import site as stock_site
    from djadmin import site as deux_site

    stock_models = sorted(
        f"{m._meta.app_label}.{m._meta.model_name}"
        for m in stock_site._registry.keys()
    )
    deux_models = sorted(
        f"{m._meta.app_label}.{m._meta.model_name}"
        for m in deux_site._registry.keys()
    )

    return JsonResponse({
        "ok": True,
        "stock_admin": {
            "url": "/admin/",
            "models": stock_models,
        },
        "admin_deux": {
            "url": "/djadmin/",
            "models": deux_models,
        },
    })


@csrf_exempt
@require_POST
def reset_view(request):
    """Re-seed the database."""
    call_command("seed_data")
    # Ensure a superuser exists for the admin panels
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser("admin", "admin@example.com", "admin")
    return JsonResponse({"ok": True})

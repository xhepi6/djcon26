"""
Test panel API for Talk 04: Django Forms in the Age of HTMx.

Provides endpoints for the interactive /test/ page. Separated from app
code so the books module stays clean.
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from books.forms import SingleFieldFormMixin
from books.models import Book
from books.views import get_all_fieldnames, get_value


def registry_view(request):
    """Return all registered single-field forms and their metadata."""
    forms = []
    for Form in SingleFieldFormMixin.__subclasses__():
        forms.append({
            "fieldname": Form.fieldname,
            "json_backed": getattr(Form, "json_backed", False),
            "class_name": Form.__name__,
            "module": Form.__module__,
        })
    return JsonResponse({"forms": forms})


def state_view(request):
    """Return all books with all their field values."""
    fieldnames = get_all_fieldnames()
    books = []
    for book in Book.objects.order_by("pk"):
        fields = {}
        for fn in fieldnames:
            fields[fn] = get_value(book, fn)
        books.append({
            "id": book.pk,
            "title": book.title,
            "fields": fields,
            "misc": book.misc,
        })
    return JsonResponse({"books": books, "fieldnames": fieldnames})


@csrf_exempt
@require_POST
def reset_view(request):
    """Delete all books and re-seed."""
    from books.management.commands.seed_books import SEED

    Book.objects.all().delete()
    for row in SEED:
        Book.objects.create(**row)
    return JsonResponse({"ok": True, "count": Book.objects.count()})

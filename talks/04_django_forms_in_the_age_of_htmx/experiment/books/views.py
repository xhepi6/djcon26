"""
Views for the single-field-form demo.

Key moves:

* ``get_forms()`` walks ``SingleFieldFormMixin.__subclasses__()`` — the implicit
  registry. Only the form whose ``fieldname`` matches a POST key gets bound,
  so unaffected forms stay unbound (no accidental validation errors).

* ``is_htmx()`` inspects the ``HX-Request`` header. Both endpoints return a
  small fragment for HTMx and a full page when requested directly by a browser.
  Same URL, two templates.

* POST success returns the display fragment (value + Edit button) so HTMx can
  swap straight back to read-mode without reloading.
"""

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from .forms import BookForm, SingleFieldFormMixin
from .models import Book


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_forms(data=None, obj=None):
    """
    Build one instance of every registered single-field form.

    - ``data`` — only bind it to the form whose ``fieldname`` is present,
      so other forms stay unbound and won't trigger validation.
    - ``obj`` — passed as ``instance``; ``JSONBackedMixin`` will use it to
      seed the input from ``obj.misc[fieldname]``.
    """
    data = data or {}
    forms_by_field = {}
    for Form in SingleFieldFormMixin.__subclasses__():
        kwargs = {"instance": obj}
        if Form.fieldname in data:
            kwargs["data"] = data
        forms_by_field[Form.fieldname] = Form(**kwargs)
    return forms_by_field


def is_htmx(request):
    """True if the request was fired by the HTMx library."""
    return request.headers.get("HX-Request") == "true"


# Cache column names once — used to decide where to read a value from.
_COLUMN_FIELDS = {f.name for f in Book._meta.fields}


def get_value(obj, fieldname):
    """Fetch a field's current value whether it's a column or lives in misc."""
    if fieldname in _COLUMN_FIELDS:
        return getattr(obj, fieldname)
    return obj.misc.get(fieldname, "")


def get_all_fieldnames():
    """Ordered list of all registered single-field-form fieldnames."""
    return [Form.fieldname for Form in SingleFieldFormMixin.__subclasses__()]


# ---------------------------------------------------------------------------
# List view — one row per book, every field independently editable
# ---------------------------------------------------------------------------


class BookListView(ListView):
    model = Book
    template_name = "books/book_list.html"
    context_object_name = "books"
    ordering = ["id"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Pre-compute (fieldname, value, label) tuples per book so the template
        # can iterate without having to know which fields exist.
        fieldnames = get_all_fieldnames()
        labels = {
            "title": "Title",
            "author": "Author",
            "year": "Year",
            "trivia": "Trivia (JSON-backed)",
            "notes": "Notes (JSON-backed)",
        }
        ctx["rows"] = [
            {
                "book": book,
                "fields": [
                    {
                        "fieldname": fn,
                        "label": labels.get(fn, fn.title()),
                        "value": get_value(book, fn),
                    }
                    for fn in fieldnames
                ],
            }
            for book in ctx["books"]
        ]
        return ctx


# ---------------------------------------------------------------------------
# Single-field GET — returns the one-field <form>
# ---------------------------------------------------------------------------


def book_field_form(request, pk, fieldname):
    """Return the one-field <form> fragment (HTMx) or full page (plain GET)."""
    book = get_object_or_404(Book, pk=pk)
    forms_by_field = get_forms(obj=book)
    if fieldname not in forms_by_field:
        return render(request, "books/404.html", status=404)
    form = forms_by_field[fieldname]
    template = "books/_field_form.html" if is_htmx(request) else "books/field_form.html"
    return render(
        request,
        template,
        {"object": book, "fieldname": fieldname, "form": form},
    )


def book_field_display(request, pk, fieldname):
    """GET — returns the display fragment (value + Edit button). Used on Cancel."""
    book = get_object_or_404(Book, pk=pk)
    return render(
        request,
        "books/_field_display.html",
        {
            "object": book,
            "fieldname": fieldname,
            "value": get_value(book, fieldname),
        },
    )


# ---------------------------------------------------------------------------
# Single-field POST — saves exactly one field
# ---------------------------------------------------------------------------


def book_field_update(request, pk, fieldname):
    """POST — validate & save one field. HTMx: return display fragment; plain: redirect."""
    if request.method != "POST":
        return HttpResponseRedirect(reverse("book-list"))

    book = get_object_or_404(Book, pk=pk)
    forms_by_field = get_forms(data=request.POST, obj=book)
    if fieldname not in forms_by_field:
        return render(request, "books/404.html", status=404)
    form = forms_by_field[fieldname]

    if form.is_bound and form.is_valid():
        form.save()
        book.refresh_from_db()
        if is_htmx(request):
            return render(
                request,
                "books/_field_display.html",
                {
                    "object": book,
                    "fieldname": fieldname,
                    "value": get_value(book, fieldname),
                },
            )
        return HttpResponseRedirect(reverse("book-list"))

    # Validation failed — re-render with errors
    template = "books/_field_form.html" if is_htmx(request) else "books/field_form.html"
    return render(
        request,
        template,
        {"object": book, "fieldname": fieldname, "form": form},
    )


# ---------------------------------------------------------------------------
# Classic one-big-form views — for comparison with the single-field pattern
# ---------------------------------------------------------------------------


class BookCreateView(CreateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"

    def get_success_url(self):
        return reverse("book-list")


class BookUpdateView(UpdateView):
    model = Book
    form_class = BookForm
    template_name = "books/book_form.html"

    def get_success_url(self):
        return reverse("book-list")

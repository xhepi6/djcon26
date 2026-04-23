"""
Forms for the single-field-form demo.

Two ideas, one file:

1. ``SingleFieldFormMixin`` — a marker that flags a form as "I only edit one
   field". Its Python side-effect is that ``__subclasses__()`` gives you a
   free registry you can walk over in a view.

2. ``JSONBackedMixin`` — store values in ``Book.misc`` instead of a column, so
   you can add new editable fields without a migration.
"""

from django import forms

from .models import Book


# ---------------------------------------------------------------------------
# Classic one-big-form (included for comparison with the single-field pattern)
# ---------------------------------------------------------------------------


class BookForm(forms.ModelForm):
    """The 'old way' — every field at once. Shown on /new/ and /<pk>/edit/."""

    template_name = "django/forms/dl.html"  # uses our <dl>-based override

    class Meta:
        model = Book
        fields = ["title", "author", "year"]


# ---------------------------------------------------------------------------
# The mixin + the per-field ModelForms
# ---------------------------------------------------------------------------


class SingleFieldFormMixin:
    """
    Every subclass of this mixin represents exactly ONE editable field.

    - ``fieldname`` — the form's single field, also the key used in URLs and
      when walking the registry (``__subclasses__()``) in ``views.get_forms``.
    - ``json_backed`` — cosmetic/introspection flag saying whether the value
      lives in a column or in ``Book.misc``.

    ``get_field()`` returns the BoundField so templates can render ONLY the
    widget, independent of the <form> wrapper. That is the whole point: you
    can inline the widget anywhere and still get Django's validation/errors.
    """

    template_name = "django/forms/dl.html"
    fieldname: str
    json_backed: bool = False

    def get_field(self):
        return self[self.fieldname]


class BookTitleForm(SingleFieldFormMixin, forms.ModelForm):
    fieldname = "title"
    json_backed = False

    class Meta:
        model = Book
        fields = ["title"]


class BookAuthorForm(SingleFieldFormMixin, forms.ModelForm):
    fieldname = "author"
    json_backed = False

    class Meta:
        model = Book
        fields = ["author"]


class BookYearForm(SingleFieldFormMixin, forms.ModelForm):
    fieldname = "year"
    json_backed = False

    class Meta:
        model = Book
        fields = ["year"]


# ---------------------------------------------------------------------------
# JSON-backed forms — fields stored in Book.misc, no migration required
# ---------------------------------------------------------------------------


class JSONBackedMixin:
    """
    Swap the normal ``instance`` handling for ``instance.misc[fieldname]``.

    - On ``__init__``: seed ``initial`` from ``instance.misc`` so the input is
      pre-populated with the current value.
    - On ``save``: write back to ``instance.misc`` and persist ``instance``.

    Works with a plain ``forms.Form`` (no model fields) — great for plugin
    fields where you don't want to touch the schema.
    """

    json_backed = True

    def __init__(self, instance=None, data=None, **kwargs):
        self.instance = instance
        if instance is not None:
            value = instance.misc.get(self.fieldname, "")
            if value != "":
                kwargs.setdefault("initial", {})[self.fieldname] = value
        super().__init__(data=data, **kwargs)

    def save(self, **_):
        # Mirror ModelForm.save's behaviour: validate, then persist.
        if self.is_valid():
            self.instance.misc[self.fieldname] = self.cleaned_data[self.fieldname]
            self.instance.save()
        return self.instance


class TriviaForm(JSONBackedMixin, SingleFieldFormMixin, forms.Form):
    """Example JSON-backed field: multi-line trivia stored in Book.misc."""

    fieldname = "trivia"
    trivia = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "cols": 40}),
        required=False,
        label="Trivia",
    )


class NotesForm(JSONBackedMixin, SingleFieldFormMixin, forms.Form):
    """Another JSON-backed field — demonstrates adding one is a class, not a migration."""

    fieldname = "notes"
    notes = forms.CharField(
        required=False,
        label="Notes",
        max_length=200,
    )

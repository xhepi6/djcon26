"""
Bonus #1 from the talk — widget context smuggling.

Widget templates get only ``{widget: {...}}`` context — no ``request``, no
``csrf_token``, no parent form. If you need to render extra attributes on an
isolated widget (think ``hx-target``, ``hx-swap``), stuff them on the widget
instance and thread them through ``get_context``.

The subtlety: Django **deep-copies** every widget off the class when the form
is instantiated (Widget.__deepcopy__ copies ``attrs`` and ``choices`` by hand).
Custom attributes you add won't survive unless you override ``__deepcopy__``.
"""

from django import forms


class HxWidgetMixin:
    """Mixin that smuggles an ``hx`` dict into widget template context."""

    def __init__(self, hx=None, **kwargs):
        super().__init__(**kwargs)
        # Copy so every widget instance gets its own dict.
        self.hx = dict(hx or {})

    def __deepcopy__(self, memo):
        # Django clones widgets when building bound fields; keep our attr alive.
        obj = super().__deepcopy__(memo)
        obj.hx = self.hx.copy()
        memo[id(self)] = obj
        return obj

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["hx"] = self.hx
        return context


class HxTextInput(HxWidgetMixin, forms.TextInput):
    """Example widget: a plain <input> with htmx attributes baked in.

    Use with a widget template (e.g. ``templates/django/forms/widgets/hxtext.html``)
    that renders ``hx-post="{{ widget.hx.post }}"`` etc.  Not wired into the
    demo views — shown here so you can drop it into ``BookTitleForm`` like::

        class BookTitleForm(SingleFieldFormMixin, forms.ModelForm):
            class Meta:
                model = Book
                fields = ["title"]
                widgets = {
                    "title": HxTextInput(hx={"post": "/books/1/title/update/"}),
                }
    """

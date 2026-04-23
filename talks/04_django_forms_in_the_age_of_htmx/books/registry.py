"""
Bonus #2 from the talk — an explicit registry via ``__init_subclass__``.

``SingleFieldFormMixin.__subclasses__()`` only sees *direct* subclasses. Once
you introduce intermediate mixins or abstract bases, grandchildren stop showing
up. This pattern avoids that: every class registers itself when Python builds
it, so the ``registry`` dict is always complete and easy to iterate.

Not used by the main demo views — it's here to show the pattern side-by-side.
"""

from django import forms


class BetterSingleFieldForm:
    """
    Use this in place of ``SingleFieldFormMixin`` when you want a plugin registry
    that survives deeper inheritance hierarchies.

    Example::

        class MyField(BetterSingleFieldForm, forms.Form):
            fieldname = "my_field"
            my_field = forms.CharField()

        # Later:
        for fieldname, form_cls in BetterSingleFieldForm.registry.items():
            ...
    """

    registry: dict = {}

    fieldname: str
    json_backed: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only register concrete subclasses (those that declare a fieldname).
        fieldname = getattr(cls, "fieldname", None)
        if fieldname:
            cls.registry[fieldname] = cls

    @classmethod
    def unregister(cls):
        cls.registry.pop(cls.fieldname, None)

    def get_field(self):
        return self[self.fieldname]


# Demo: a plugin field registered via the better registry.
# (Not wired into the views — try it in the Django shell:
#   >>> from books.registry import BetterSingleFieldForm
#   >>> BetterSingleFieldForm.registry
# )
class ColorField(BetterSingleFieldForm, forms.Form):
    fieldname = "color"
    color = forms.CharField(max_length=32, required=False)

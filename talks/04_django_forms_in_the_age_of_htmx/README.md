# Django Forms in the Age of HTMx: The Single Field Form

> **Speaker:** Hanne Moa — works on [Argus](https://github.com/Uninett/Argus) at Sikt/Uninett (Norwegian research network)
> **Event:** DjangoCon Europe 2026 (Greece)

## What is this about?

HTMx lets you treat any HTML tag as a form trigger — no `<form>` needed. This talk shows how to plug that into Django's `Form` class so you can edit **one field at a time**, inline: click the displayed value, swap it with an `<input>`, hit Enter, server saves that field alone and swaps the value back. Hanne converted Argus (a production alert system) from a React SPA to Django + HTMx in 2024–2025 and distilled the patterns into a small demo repo, [`singlefieldform`](https://github.com/Uninett/singlefieldform).

## The Problem

- Django forms are designed as "all fields at once" — editing one field inline needs custom plumbing
- Django splits a big form into several pages gets ugly fast (the talk opens with a 2014 story of a 4-part form that mutated every 6 months and still haunts the speaker)
- Widget templates receive only `{widget: ...}` — no `request`, no `csrf_token`, no parent form — so rendering an `<input>` **without a `<form>` wrapper** is awkward
- Making forms pluggable (e.g. per-tenant custom fields) usually means per-project glue

## The Solution

- **One form per field.** Each field is a `ModelForm` (or plain `Form`) with exactly one field plus a `fieldname` marker
- **Marker mixin doubles as a registry.** `SingleFieldFormMixin.__subclasses__()` gives you every single-field form for free
- **HTMx for the swap.** Edit button does `hx-get` → server returns the one-field `<form>` fragment → submit POSTs → server saves and returns the updated display fragment
- **JSON-backed forms for plugin fields.** A mixin that reads/writes `instance.misc[fieldname]` lets you add new editable fields **without migrations**
- **Bonus 1: widget context smuggling.** A widget mixin that survives `__deepcopy__` and injects extra context in `get_context` — so an isolated widget template can render `hx-target`, `hx-swap` etc. attributes
- **Bonus 2: explicit registry.** `__init_subclass__` + a `registry` dict beats `__subclasses__()` — the latter only sees *direct* subclasses, which breaks once you introduce intermediate base classes

## How to Use It

### Install

```bash
pip install "Django>=5.2"
# HTMx is loaded from CDN in base.html, no Python dependency
```

### 1. The marker mixin

```python
# books/forms.py
from django import forms
from .models import Book


class SingleFieldFormMixin:
    """Each subclass edits exactly one field. `__subclasses__()` = free registry."""
    template_name = "django/forms/dl.html"
    fieldname: str
    json_backed: bool

    def get_field(self):
        """Return the BoundField so a template can render JUST the widget."""
        return self[self.fieldname]
```

### 2. One ModelForm per model field

```python
class BookTitleForm(SingleFieldFormMixin, forms.ModelForm):
    fieldname = "title"
    json_backed = False
    class Meta:
        model = Book
        fields = ["title"]


class BookYearForm(SingleFieldFormMixin, forms.ModelForm):
    fieldname = "year"
    json_backed = False
    class Meta:
        model = Book
        fields = ["year"]
```

### 3. The registry-walking helper

```python
def get_forms(data=None, obj=None):
    """Walk every subclass. Bind data only to the form whose field was submitted."""
    data = data or {}
    forms = {}
    for Form in SingleFieldFormMixin.__subclasses__():
        kwargs = {"instance": obj}
        if Form.fieldname in data:
            kwargs["data"] = data
        forms[Form.fieldname] = Form(**kwargs)
    return forms
```

### 4. Plugin fields without migrations (JSONField + mixin)

```python
class JSONBackedMixin:
    """Stores the value in instance.misc[fieldname] instead of a column."""
    json_backed = True

    def __init__(self, instance=None, data=None, **kwargs):
        self.instance = instance
        if instance is not None:
            value = instance.misc.get(self.fieldname, "")
            if value:
                kwargs.setdefault("initial", {})[self.fieldname] = value
        super().__init__(data=data, **kwargs)

    def save(self, **_):
        if self.is_valid():
            self.instance.misc[self.fieldname] = self.cleaned_data[self.fieldname]
            self.instance.save()


class TriviaForm(JSONBackedMixin, SingleFieldFormMixin, forms.Form):
    fieldname = "trivia"
    trivia = forms.CharField(widget=forms.Textarea, required=False)
```

Adding a new field to the UI = adding one class. No migration, no model change.

### 5. View: one endpoint, two templates

```python
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect
from django.urls import reverse


def is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def book_field_form(request, pk, fieldname):
    """GET — return the one-field <form>. Fragment for HTMx, full page otherwise."""
    book = get_object_or_404(Book, pk=pk)
    form = get_forms(obj=book)[fieldname]
    template = "books/_field_form.html" if is_htmx(request) else "books/field_form.html"
    return render(request, template, {"object": book, "fieldname": fieldname, "form": form})


def book_field_update(request, pk, fieldname):
    """POST — save one field, return updated display fragment (HTMx) or redirect."""
    book = get_object_or_404(Book, pk=pk)
    form = get_forms(data=request.POST, obj=book)[fieldname]
    if form.is_valid():
        form.save()
        if is_htmx(request):
            return render(request, "books/_field_display.html",
                          {"object": book, "fieldname": fieldname, "value": get_value(book, fieldname)})
        return HttpResponseRedirect(reverse("book-list"))
    # validation failed — re-render with errors
    template = "books/_field_form.html" if is_htmx(request) else "books/field_form.html"
    return render(request, template, {"object": book, "fieldname": fieldname, "form": form})
```

### 6. Templates: the HTMx-specific bits

Display partial — what the user clicks on:

```html
{# _field_display.html #}
<span class="value">{{ value|default:"(empty)" }}</span>
<button type="button"
        hx-get="{% url 'book-field-form' pk=object.pk fieldname=fieldname %}"
        hx-target="closest .field"
        hx-swap="innerHTML">Edit</button>
```

Form fragment — what replaces the display:

```html
{# _field_form.html #}
<form method="post"
      hx-post="{% url 'book-field-update' pk=object.pk fieldname=fieldname %}"
      hx-target="closest .field"
      hx-swap="innerHTML">
    {% csrf_token %}
    {{ form.get_field }}
    <button type="submit">Save</button>
    <button type="button"
            hx-get="{% url 'book-field-display' pk=object.pk fieldname=fieldname %}"
            hx-target="closest .field" hx-swap="innerHTML">Cancel</button>
</form>
```

Note `{{ form.get_field }}` calls the mixin method — it renders the BoundField directly, **no `<form>` wrapper, no `form.as_p`**. Pair this with `FORM_RENDERER` overrides (put `'django.forms'` in `INSTALLED_APPS` and drop `django/forms/field.html` in your templates dir) to control exactly how the widget + label + errors come out.

### 7. Bonus — widget context smuggling

If the widget template is rendered in total isolation (no parent form context), you need to inject `hx-*` attributes into the widget itself:

```python
class HxWidgetMixin:
    def __init__(self, hx=None, **kwargs):
        super().__init__(**kwargs)
        self.hx = hx or {}

    def __deepcopy__(self, memo):
        # Django deep-copies widgets off the class; custom attrs must survive.
        obj = super().__deepcopy__(memo)
        obj.hx = self.hx.copy()
        memo[id(self)] = obj
        return obj

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["hx"] = self.hx
        return context


class HxTextInput(HxWidgetMixin, forms.TextInput): ...
```

Widget template can now do `hx-target="{{ widget.hx.target }}"`.

### 8. Bonus — a real registry

```python
class BetterSingleFieldForm(SingleFieldFormMixin):
    registry: dict = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if getattr(cls, "fieldname", None):
            cls.registry[cls.fieldname] = cls
```

Drop `__subclasses__()` in favour of `BetterSingleFieldForm.registry`. Works across inheritance levels, supports unregister, plugin-load order is deterministic.

## Experiment

The `experiment/` folder has a runnable Django project with all of the above wired up.

```bash
cd experiment
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_books
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

| Route | What it shows |
|---|---|
| `/` | Book list with inline edit — every field has its own Edit button (HTMx) |
| `/<pk>/<fieldname>/` | GET — returns the one-field form. Full page if opened directly, fragment if requested by HTMx. Try both |
| `/<pk>/<fieldname>/update/` | POST — saves one field, returns updated display fragment |
| `/new/` | Classic one-big-form create — for comparison |
| `/<pk>/edit/` | Classic one-big-form edit — for comparison |

Noteworthy files:
- `books/forms.py` — mixins, per-field forms, JSON-backed `TriviaForm` and `NotesForm`
- `books/views.py` — `get_forms()` registry walk, `is_htmx()` branching
- `books/templates/books/_field_display.html` and `_field_form.html` — the two HTMx partials
- `books/widgets.py` — `HxWidgetMixin` demo (Bonus #1)
- `books/registry.py` — `__init_subclass__` registry (Bonus #2)
- `templates/django/forms/dl.html` — global form layout override (project-wide)

The `misc` JSONField on `Book` stores Trivia and Notes — open `/admin`-equivalent data via `python manage.py seed_books --show` to see how plugin fields live alongside columns.

## Key Takeaways

- **One form per field + a marker mixin** is enough to get an implicit registry. `__subclasses__()` is the cheapest registry in Python
- **HTMx turns every `<span>` into a form.** The server side stays 100% Django forms — no new library
- **`HX-Request` header** tells you fragment-vs-page. Same view, two templates
- **JSONField + JSON-backed mixin = plugin fields without migrations**. Huge for multi-tenant / per-customer custom fields
- **`__init_subclass__` beats `__subclasses__()`** once inheritance gets more than one level deep
- **Widget context smuggling** (deep-copy-safe custom attrs + `get_context`) lets a widget template render in total isolation with everything it needs

## Q&A Highlights

- **Granular permissions on one-field forms?** Subclass per role or add a `visible_to(user)` hook in the mixin; the registry can filter before presenting fields. Field-level auth in Django has never been great — this at least makes it explicit
- **Why HTMx over React for Argus?** Team size and complexity — Argus was a React SPA maintained by a small ops-adjacent team; switching to Django MPA + HTMx cut the code surface and let backend devs own the UI
- **CSRF with HTMx?** Keep `{% csrf_token %}` inside the fragment (simplest), or set `hx-headers='{"X-CSRFToken": "..."}'` on `<body>` and read the cookie. The demo uses the in-form token

## Links

- Demo repo: <https://github.com/Uninett/singlefieldform>
- Slides: <https://github.com/Uninett/singlefieldform/tree/main/slides>
- Argus (production HTMx conversion): <https://github.com/Uninett/Argus>
- Argus live demo: <https://argus-demo.uninett.no/>
- HTMx: <https://htmx.org>
- Django widget rendering: <https://docs.djangoproject.com/en/5.2/ref/forms/widgets/>
- Django form rendering (`FORM_RENDERER`, `django.forms`): <https://docs.djangoproject.com/en/5.2/ref/forms/renderers/>

---
*Summarized at DjangoCon Europe 2026*

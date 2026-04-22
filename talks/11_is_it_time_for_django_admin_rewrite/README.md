# Is It Time for a Django Admin Rewrite?

> **Speaker:** Emma Delescolle — Django Steering Council member, founder of LevIT (Belgium)
> **Event:** DjangoCon Europe 2026

## What is this about?

Django's admin is 20 years old. It's powerful out of the box, but customizing it means fighting a framework-inside-a-framework that doesn't follow modern Django patterns. Django-Admin-Deux is a ground-up rewrite that generates admin views from Django's own generic views, uses a plugin system for extensibility, and feels like writing regular Django code.

## The Problem

- **The admin is a framework inside a framework** — it has its own patterns, its own view system, its own template hierarchy. Learning Django doesn't mean you know how to extend the admin
- **Third-party packages collide** — add django-import-export, django-filter, custom actions, inline editors, and a theme. They all override templates and monkey-patch internals. They clash
- **No plugin architecture** — the admin wasn't designed for composable extensions. Every package reinvents its own hook points
- **20 years of legacy** — class-based views, dataclasses, type hints, Django's generic views — none of these existed when the admin was written. It doesn't use them
- **Community demand** — of the first new feature requests on Django's GitHub tracker, a disproportionate number were for the admin. Issue #70 simply says "we should rethink the admin"
- **Customization hits a wall** — simple things (row-level actions, custom columns, form layouts) require deep template overrides or subclassing internals

## The Solution

Django-Admin-Deux takes a different approach:

- **Factory-generated views** — at startup, a view factory dynamically creates view classes using `type()`, composing base views + plugin mixins. The result is standard Django class-based views
- **Actions as recipes** — every operation (list, create, update, delete) is an "Action" — a dataclass describing what view to generate, what permissions to check, what template to use. Custom actions (export PDF, send notification) work the same way as CRUD
- **Plugin-first design** — built on Simon Willison's `djp` (which uses `pluggy` from pytest). Plugins auto-register on `pip install`. Even core CRUD is implemented as a plugin
- **Django-native** — if you know Django generic views, forms, and querysets, you know how to extend admin-deux. No new framework to learn
- **Side-by-side migration** — runs on a separate URL (`/djadmin/`) alongside stock admin. Migrate one model at a time

## How to Use It

### Install

```bash
# Basic install
pip install django-admin-deux

# With all plugins (filters, formset, docs)
pip install django-admin-deux[full]
```

### Setup

```python
# settings.py
from djadmin import djadmin_apps

INSTALLED_APPS = [
    "django.contrib.admin",       # stock admin can stay
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    *djadmin_apps(),              # auto-orders admin-deux and its plugins
    "myapp",
]
```

```python
# urls.py
from django.contrib import admin
from django.urls import path, include
from djadmin import site

urlpatterns = [
    path("admin/", admin.site.urls),        # stock admin
    path("djadmin/", include(site.urls)),    # admin-deux
    path("accounts/", include("django.contrib.auth.urls")),
]
```

### Register models

Create `djadmin.py` in your app (not `admin.py`):

```python
# myapp/djadmin.py
from djadmin import ModelAdmin, register
from .models import Product

@register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "sku", "category", "price", "status"]
    list_filter = ["status", "category"]
    search_fields = ["name", "sku"]
```

The API is intentionally near-identical to stock admin. Only the import changes.

### Enhanced list_display with Column objects

```python
from djadmin import ModelAdmin, register, Column
from djadmin.dataclasses import Filter, Order

@register(Product)
class ProductAdmin(ModelAdmin):
    list_display = [
        "name",                                                # plain string works
        Column("sku", label="SKU Code", classes="font-mono"),  # styled column
        Column("category", filter=True, order=True),           # sortable + filterable
        Column("price", order=True, filter=Filter(lookup_expr=["gte", "lte"])),
    ]
```

Mix plain strings and `Column` objects freely. `filter=True` gives exact-match filtering; `Filter(...)` for range lookups, custom widgets, method-based filters.

### Form layout customization

```python
from djadmin import Layout, Field, Fieldset, Row

@register(Author)
class AuthorAdmin(ModelAdmin):
    layout = Layout(
        Fieldset("Personal Information",
            Row(
                Field("first_name", css_classes=["flex-1", "pr-2"]),
                Field("last_name", css_classes=["flex-1", "pl-2"]),
            ),
            Field("birth_date", label="Date of Birth"),
        ),
        Fieldset("Biography",
            Field("bio", widget="textarea", attrs={"rows": 8}),
        ),
    )
```

You can also use `create_layout` and `update_layout` for different forms on create vs. update.

### The Action system

Three action types:

| Type | Scope | Examples |
|------|-------|---------|
| **General** | Model-level | List, Add New, Dashboard |
| **Record** | Single object | Edit, Delete, Publish |
| **Bulk** | Multiple objects | Bulk delete, Export CSV |

CRUD operations are just actions. Adding "export as PDF" works the same way as "edit" — no special cases.

### Writing a plugin

```python
# my_plugin.py
from djadmin.plugins import hookimpl

@hookimpl
def djadmin_provides_features():
    return ["search", "filter"]

@hookimpl
def djadmin_get_action_view_mixins(action):
    from djadmin.plugins.core.actions import ListAction
    from .mixins import SearchMixin
    return {ListAction: [SearchMixin]}
```

Plugins auto-register on `pip install` when using `djadmin_apps()`. No manual `INSTALLED_APPS` entries needed.

## Available Plugins

| Plugin | Package | What it does |
|--------|---------|-------------|
| **Core** | built-in | CRUD actions, search |
| **djadmin-filters** | `djadmin-filters` | Filtering, ordering, sidebar (uses django-filter) |
| **djadmin-formset** | `djadmin-formset` | Form rendering, inlines, drag-and-drop (uses django-formset) |
| **djadmin-classy-doc** | `djadmin-classy-doc` | Auto-generated view docs (like CCBV for your admin) |
| **djadmin-rest2** | via `djrest2` | REST API views as a plugin — proves the architecture |

## Migration from Stock Admin

| Effort level | What |
|-------------|------|
| **No effort** | Non-admin packages (celery, cors-headers), form field overrides |
| **Medium** | Packages with admin compat layers (django-import-export — write a short plugin) |
| **Larger** | Theme replacements, view replacements (treebeard, mptt), sidebar widgets (reversion) |

## Experiment

The `experiment/` folder has a runnable Django project with both stock admin and admin-deux side by side. It demonstrates model registration, enhanced columns, form layouts, and plugins.

```bash
cd experiment
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py createsuperuser
python manage.py runserver
```

What you can try:

| URL | What it shows |
|-----|--------------|
| `/admin/` | Stock Django admin — same models, for comparison |
| `/djadmin/` | Admin-deux — enhanced columns, filters, layouts |
| `python manage.py djadmin_inspect` | Introspect registered ModelAdmins and their actions |

Key files:
- `catalog/djadmin.py` — admin-deux registration with Column objects and Layout
- `catalog/admin.py` — stock admin registration for the same models (comparison)
- `catalog/models.py` — Product, Category, Author models
- `config/urls.py` — both admins mounted side by side

## Key Takeaways

- **The admin is Django's most-requested area for improvement** — the community wants change, not just patches
- **Admin-deux uses Django's own tools** — generic views, forms, querysets. If you know Django, you know how to extend it
- **Plugin-first means no more collisions** — `djp`/`pluggy` gives each extension clean hook points instead of template overrides
- **Migration is gradual** — run both admins side by side, move one model at a time
- **This is alpha software** — 0.1.6, 720 tests, 82% coverage. The API will change. But the architecture is solid and ready for feedback

## Q&A Highlights

- **Why does it look like the old admin?** — theming is a plugin. The default uses plain CSS with no framework. Building a custom theme is straightforward since CSS classes are exposed, but expect some churn during alpha
- **Can it do live updates (SSE/WebSocket)?** — yes, the plugin system supports registering JavaScript and CSS per view type. A plugin could add HTMX, server-sent events, or any client-side behavior
- **How does it handle custom widgets?** — stock Django form/widget customization still works. For polished form rendering, use the `djadmin-formset` plugin which integrates django-formset (client-side validation, conditional fields, drag-and-drop)

## Links

- Source code: https://codeberg.org/emmaDelescolle/django-admin-deux
- PyPI: https://pypi.org/project/django-admin-deux/
- Docs: https://django-admin-deux.readthedocs.io/
- Blog post: https://emma.has-a.blog/articles/django-admin-deux-bringing-admin-back-to-django/
- Slides (talk): https://levit.be/slides/admin-deux_djceu26.html
- Slides (workshop): https://levit.be/slides/admin-deux_workshop_djceu26.html
- Django new features issue #70: https://github.com/django/new-features/issues/70
- djp (plugin system): https://github.com/simonw/djp

---
*Summarized at DjangoCon Europe 2026*

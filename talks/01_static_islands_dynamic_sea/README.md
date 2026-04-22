# Static Islands in a Dynamic Sea

> **Speaker:** Carlton Gibson — Django core contributor, Steering Council member, co-host of Django Chat podcast, former DSF Fellow
> **Event:** DjangoCon Europe 2026 (Greece)

## What is this about?

Django is dynamic by design. Trying to force static types onto it fights the framework. Instead, build **typed Python classes on top of Django's ORM** — keep Django as-is, add type safety where it helps. The library **Mantle** does exactly this.

## The Problem

- **Fat models grow out of control** — display logic, queries, serialization, validation all crammed into one model class
- **The ORM fetches too much** — by default it loads all fields, even ones you don't need
- **N+1 queries are easy to hit** — accessing `bookmark.user.username` in a loop fires one query per bookmark
- **Static types don't fit Django's dynamic core** — the ORM uses metaclasses, introspection, and dynamic attributes that type checkers can't follow
- **`select_related`/`prefetch_related` are opt-in** and break when models change

## The Solution

Build **typed dataclasses** (using `attrs`) that define the exact shape of data you need. Use **Mantle** to bridge from the ORM to those shapes efficiently.

- Your business logic lives in plain, typed Python classes — easy to test, easy to read
- Mantle auto-generates optimized ORM queries (only the fields you declared)
- Related objects are prefetched automatically — no N+1
- Validation is separate and composable
- DRF integration replaces serializers with shape classes

## How to Use It

### Install

```bash
pip install django-mantle          # core
pip install django-mantle-drf      # if using Django REST Framework
```

### 1. Define your model (normal Django)

```python
from django.db import models
from django.contrib.auth.models import User

class Bookmark(models.Model):
    url = models.URLField()
    comment = models.TextField(blank=True)
    favourite = models.BooleanField(default=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
```

### 2. Define a data shape (what you actually need)

```python
from attrs import define

@define
class BookmarkData:
    url: str
    comment: str
    favourite: bool
```

This is your "static island" — a plain typed class, no Django magic.

### 3. Query with Mantle

```python
from mantle import Query

# Get all bookmarks as typed objects
bookmarks = Query(Bookmark.objects.all(), BookmarkData).all()
# type: list[BookmarkData]

# Get one
bookmark = Query(Bookmark.objects.filter(pk=1), BookmarkData).get()
# type: BookmarkData
```

Mantle generates the ORM query with `only()` applied — it fetches just `url`, `comment`, and `favourite`. Nothing extra.

### 4. Nested related data (solves N+1)

```python
@define
class UserData:
    username: str

@define
class BookmarkData:
    url: str
    comment: str
    favourite: bool
    user: UserData
```

```python
bookmarks = Query(Bookmark.objects.all(), BookmarkData).all()
```

Mantle sees the nested `UserData` and auto-generates `select_related("user")` with `only("user__username")`. Two queries max, regardless of how many bookmarks.

### 5. Custom field logic with @overrides

When you need computed fields or reshaping:

```python
from attrs import define
from django_readers import qs, producers
from django.db.models import F
from mantle import Query, overrides

@overrides({
    "username": (
        qs.annotate(username=F("user__username")),
        producers.attr("username"),
    )
})
@define
class BookmarkFlat:
    id: int
    title: str
    favourite: bool
    username: str  # pulled from related user, flattened
```

### 6. Validation

```python
from mantle import compose_validators, create, unique_field, update

bookmark_validator = compose_validators(
    unique_field("url"),
)

# Create with validation
new_bookmark = create(
    Bookmark,
    BookmarkData(url="https://example.com", comment="Test", favourite=True),
    validator=bookmark_validator,
)
# type: Bookmark

# Update with validation
updated = update(
    new_bookmark,
    BookmarkData(url="https://example.com/updated", comment="Updated", favourite=False),
    validator=bookmark_validator,
)
```

### 7. DRF Integration (django-mantle-drf)

Replace serializers with shape classes:

```python
from mantle_drf.generics import ListCreateAPIView
from .models import Bookmark

import attrs

@attrs.define
class BookmarkShape:
    url: str
    title: str
    comment: str = ""

class BookmarkList(ListCreateAPIView):
    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape  # instead of serializer_class
```

That's it. `GET` returns shaped data, `POST` structures incoming JSON into your shape and persists it.

Full CRUD with viewsets:

```python
from mantle_drf.viewsets import ModelViewSet

class BookmarkViewSet(ModelViewSet):
    queryset = Bookmark.objects.all()
    shape_class = BookmarkShape
```

OpenAPI schema generation works with `drf-spectacular` — register in your `AppConfig.ready()`:

```python
class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        import mantle_drf.schema  # noqa: F401
```

## How It Works Under the Hood

Mantle uses **django-readers** internally. The flow:

```
attrs class → readers spec → (prepare, project) → optimized queryset → dicts → cattrs → attrs instances
```

1. Your `@define` class is converted to a readers spec (list of field names and relations)
2. `django-readers` processes it into a `prepare` function (optimizes the queryset) and `project` function (extracts data from instances)
3. `cattrs` structures the raw dicts into your typed attrs instances

You can see the raw spec:

```python
from mantle import to_spec
spec = to_spec(BookmarkData)
# ['url', 'comment', 'favourite']
```

## Experiment

This folder is a runnable Django project with all the examples above. Try it:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Then open:

- **`/test/`** — interactive test panel with all endpoints, explanations, and a side-by-side N+1 comparison
- **`/api/docs/`** — Swagger UI for the DRF endpoints
- **`/admin/`** — Django admin for managing bookmarks

To see query optimization without the server:

```bash
python manage.py compare_queries
```

Key files:
- `bookmarks/shapes.py` — the data shapes (static islands)
- `bookmarks/views.py` — DRF views + plain Django views using Mantle
- `bookmarks/models.py` — standard Django model

## Key Takeaways

- **Don't fight Django's dynamic nature** — build typed layers on top instead
- **Separate concerns**: ORM models for database, attrs classes for business logic
- **Mantle auto-optimizes queries** — no manual `only()`, `select_related()`, or `prefetch_related()`
- **Adopt incrementally** — start with one view, one shape class. No big rewrite needed
- **DRY applies within concerns, not across them** — it's OK to "repeat" a field name in your model and your data shape; they serve different purposes

## Q&A Highlights

- **Type checker?** Carlton uses **pyright** personally
- **Forms?** Not yet supported but planned — idea is clean data from forms goes into attrs classes via cattrs
- **Incremental adoption?** Start with a single retrieve endpoint. Define one shape. See how it feels. Then expand
- **Production ready?** Carlton uses it in production. Core query flow is stable. New features may be added but no arbitrary breaking changes expected
- **Django Ninja?** Possible in theory but not tested. Mantle's query/shape flow is framework-agnostic; the DRF integration is a separate package

## Links

- Docs: https://noumenal.es/mantle/
- DRF docs: https://noumenal.es/mantle-drf/
- Source: https://codeberg.org/carltongibson/django-mantle
- PyPI: `django-mantle` / `django-mantle-drf`
- Under the hood: [django-readers](https://github.com/dabapps/django-readers)

---
*Summarized at DjangoCon Europe 2026*

"""
Data shapes — the "static islands" on top of Django's dynamic ORM.

Each shape defines exactly what data you need. Mantle generates
optimized queries from these automatically.
"""

import attrs
from django.db.models import F
from django_readers import producers, qs

from mantle import overrides


# -- Basic shape: just the fields you need --

@attrs.define
class BookmarkData:
    url: str
    title: str
    comment: str
    favourite: bool


# -- With nested related data (solves N+1 automatically) --

@attrs.define
class UserData:
    username: str


@attrs.define
class BookmarkWithUser:
    url: str
    title: str
    comment: str
    favourite: bool
    user: UserData


# -- Flattened: pull related fields up using @overrides --

@overrides({
    "username": (
        qs.annotate(username=F("user__username")),
        producers.attr("username"),
    )
})
@attrs.define
class BookmarkFlat:
    id: int
    url: str
    title: str
    favourite: bool
    username: str


# -- DRF shape for API responses --

@attrs.define
class BookmarkShape:
    url: str
    title: str
    comment: str = ""


# -- Write shape: includes user_id so mantle.create() can assign the FK --

@attrs.define
class BookmarkWriteData:
    url: str
    title: str
    comment: str
    favourite: bool
    user_id: int

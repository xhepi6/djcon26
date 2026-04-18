# Role-Based Access Control in Django

> **Speaker:** Gergő Simonyi — engineer at [authentik](https://github.com/goauthentik/authentik), an open-source identity provider / authentication company.
> **Event:** DjangoCon Europe 2026

## What is this about?

Django ships with model-level permissions. `django-guardian` adds object-level permissions on top. That's enough for most apps — and wasn't enough for authentik's enterprise customers, who wanted **group hierarchies, just-in-time access, permission delegation, and custom (non-CRUD) permissions**. This talk walks the journey from `ModelBackend` → Guardian → a custom RBAC backend with a **role hierarchy** and a **transitive-closure cache** so a permission check stays a single SQL query regardless of how deep the tree gets.

## The Problem

What built-in Django gives you:

- `user.has_perm("books.change_book")` — model-level, granted via `auth_user_user_permissions` or through `Group`
- `ModelBackend.has_perm` short-circuits on `is_superuser` and falls through on non-matches (returns `False`, not `None` — more on that below)
- Multiple `AUTHENTICATION_BACKENDS` chain: each returns `True` / `False` / `PermissionDenied` (hard stop) / `None` (pass to next)

What Guardian adds:

- Object-level perms — `user.has_perm("books.change_book", book)`
- A second backend (`ObjectPermissionBackend`) on the chain
- Tables: `UserObjectPermission`, `GroupObjectPermission`, per-model generic FK to the target

What customers wanted that neither covers:

- **Group hierarchy** — parent group's perms flow to children (and grandchildren, and…)
- **Just-in-time access** — grant "admin on this project" for the next hour
- **Permission delegation** — user-to-user ("share my access with Bob while I'm on holiday")
- **Custom, non-CRUD permissions** — not `change_x` / `delete_x`, but `copy_book`, `archive_invoice`, `approve_payout`

The first attempt bolted a `Role` layer on top of Guardian + parent FKs on `Group`. Guardian didn't know about the hierarchy, so every check walked **user → group → parent → parent → ... → role → permission** manually — N queries per check. It worked in demos. It died in production.

## The Solution

Three moves:

1. **Strip Django's built-in authz** — subclass `ModelBackend` so all its `has_perm` / `get_*_permissions` methods return `False` / empty. Authentication still works; authorisation always falls through to your backend. (authentik calls this `ModelBackendNoAuthz`.)
2. **Add a single custom backend** that answers `has_perm(user, perm, obj=None)` directly against your RBAC tables.
3. **Cache the role hierarchy.** Store a **transitive closure**: one row per `(ancestor, descendant, depth)` pair. Rebuild on role-graph changes. A permission check collapses to a single query: *user's direct roles → all ancestors via closure → any of those roles hold the permission?*

Design:

- **`Role`** with `parent` FK — a DAG (kept acyclic by construction) of roles.
- **`RoleAncestry`** — the closure cache. `(ancestor, descendant, depth)`. In authentik's real code this is a PostgreSQL *materialized view* refreshed by a `pgtrigger` after every insert/update/delete on the edge table. In this experiment we keep it in a regular Django model updated by a `post_save` / `post_delete` signal — same semantics, SQLite-compatible, easier to read.
- **`UserRole`** — the assignment. A user holds a role, optionally scoped to a specific object (`content_type` + `object_id`), optionally with `expires_at` for just-in-time.
- **Permissions** reuse Django's `auth.Permission` rows. Custom (non-CRUD) perms are declared with `Meta.permissions = [("copy_book", "...")]` — no extra machinery.

The whole `has_perm` is ~10 lines of ORM. The closure does the heavy lifting.

## How to Use It

### Install

```bash
pip install "Django>=5.2"
# In production with Postgres: "django-pgtrigger" for the real authentik-style MV refresh.
```

### 1. Strip `ModelBackend`'s authz half

```python
# rbac/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class ModelBackendNoAuthz(ModelBackend):
    """Keep authenticate(); silence every authz method so the chain always falls
    through to the RBAC backend. Direct port of authentik's ModelBackendNoAuthz."""
    def get_user_permissions(self, user_obj, obj=None): return set()
    def get_group_permissions(self, user_obj, obj=None): return set()
    def get_all_permissions(self, user_obj, obj=None): return set()
    def has_perm(self, user_obj, perm, obj=None): return False
    def has_module_perms(self, user_obj, app_label): return False
    def with_perm(self, perm, is_active=True, include_superusers=True, obj=None):
        return get_user_model().objects.none()
```

```python
# settings.py
AUTHENTICATION_BACKENDS = [
    "rbac.backends.ModelBackendNoAuthz",  # authn only
    "rbac.backends.RBACBackend",          # authz
]
```

### 2. The Role / assignment / closure models

```python
# rbac/models.py
class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children",
    )
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")


class RoleAncestry(models.Model):
    """Transitive closure. (A, D, k) = A is an ancestor of D at distance k.
    Includes (R, R, 0) self-links so a single join covers 'role R itself or any
    ancestor of R'."""
    ancestor   = models.ForeignKey(Role, related_name="descendant_links", on_delete=models.CASCADE)
    descendant = models.ForeignKey(Role, related_name="ancestor_links",   on_delete=models.CASCADE)
    depth      = models.PositiveIntegerField()

    class Meta:
        unique_together = [("ancestor", "descendant")]


class UserRole(models.Model):
    """A user holds a role. Optionally scoped to a specific object (object-level
    perm) and/or time-bounded (just-in-time)."""
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rbac_roles")
    role    = models.ForeignKey(Role, on_delete=models.CASCADE)

    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id    = models.PositiveIntegerField(null=True, blank=True)
    scope        = GenericForeignKey("content_type", "object_id")

    expires_at = models.DateTimeField(null=True, blank=True)
```

### 3. Keep the closure fresh

```python
# rbac/signals.py
@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
def _rebuild_closure(sender, **kwargs):
    rebuild_role_ancestry()   # see experiment/rbac/closure.py

def rebuild_role_ancestry():
    with transaction.atomic():
        RoleAncestry.objects.all().delete()
        roles = list(Role.objects.all())
        rows  = [RoleAncestry(ancestor=r, descendant=r, depth=0) for r in roles]
        by_id = {r.pk: r for r in roles}
        for r in roles:
            cur, depth = r, 0
            seen = {r.pk}
            while cur.parent_id and cur.parent_id not in seen:
                depth += 1
                rows.append(RoleAncestry(ancestor_id=cur.parent_id, descendant=r, depth=depth))
                seen.add(cur.parent_id)
                cur = by_id[cur.parent_id]
        RoleAncestry.objects.bulk_create(rows)
```

> In authentik the edges live in `authentik_core_groupparentage`, the closure is the **materialized view** `authentik_core_groupancestry`, and a `pgtrigger` `AFTER INSERT/UPDATE/DELETE` on the edge table runs `REFRESH MATERIALIZED VIEW CONCURRENTLY …`. Semantically identical, faster at scale, but needs Postgres.

### 4. The single-query `has_perm`

```python
# rbac/backends.py
class RBACBackend:
    def authenticate(self, request, **creds):
        return None  # authentication handled by ModelBackendNoAuthz

    def has_perm(self, user_obj, perm, obj=None):
        if not user_obj.is_active:
            return False
        if user_obj.is_superuser:
            return True
        try:
            app_label, codename = perm.split(".", 1)
        except ValueError:
            return False

        now = timezone.now()
        direct = UserRole.objects.filter(user=user_obj).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
        if obj is None:
            direct = direct.filter(content_type__isnull=True)
        else:
            ct = ContentType.objects.get_for_model(obj)
            direct = direct.filter(
                Q(content_type__isnull=True) |
                Q(content_type=ct, object_id=obj.pk)
            )

        # Any ancestor (including self) of a directly-held role holds the permission?
        # R.descendant_links = RoleAncestry rows where ancestor=R, so
        # descendant_links__descendant__in=<held roles> reads as
        # "R is an ancestor of some role the user holds".
        return Role.objects.filter(
            descendant_links__descendant__in=direct.values("role"),
            permissions__content_type__app_label=app_label,
            permissions__codename=codename,
        ).exists()
```

One query. No recursion. The closure took the depth out of the problem.

### 5. Custom (non-CRUD) permissions

No new machinery — just Django:

```python
# library/models.py
class Book(models.Model):
    title = models.CharField(max_length=200)
    class Meta:
        permissions = [
            ("copy_book",    "Can copy a book"),
            ("archive_book", "Can archive a book"),
        ]
```

Bind to a role exactly like a built-in:

```python
archiver = Role.objects.create(name="archiver")
archiver.permissions.add(Permission.objects.get(codename="archive_book"))
```

## Experiment

The `experiment/` folder has a runnable Django project that demonstrates the whole design: role hierarchy, closure cache, object-level assignments, just-in-time expiry, and custom perms.

```bash
cd experiment
pip install -r requirements.txt
python manage.py migrate

python manage.py seed_data          # users, roles, books, assignments
python manage.py show_rbac          # hierarchy tree + closure + every user's effective access
python manage.py demo_checks        # a table of canonical has_perm() calls + results
python manage.py check_perm alice library.change_book                    # global model-level
python manage.py check_perm bob   library.change_book --book "Dune"      # object-level
python manage.py check_perm carol library.add_book   --sql               # print the SQL
python manage.py demo_jit           # watch carol's librarian role expire in real time
```

Canonical scenario (what `seed_data` builds):

```
Roles (hierarchy):
  viewer       → view_book
    └─ editor  → change_book       (inherits view_book)
        └─ librarian → add_book, delete_book   (inherits view_book, change_book)
  archiver     → archive_book      (custom perm, separate root)

Users:
  alice     : editor       (global)
  bob       : viewer       (global)
              editor       (scoped to Book "Dune")
  carol     : librarian    (global, expires in 10s — just-in-time)
  dave      : archiver     (global)
  admin     : Django superuser
```

What `demo_checks` prints:

```
user    perm                     object       expected  actual   via
-----------------------------------------------------------------------------------------
alice   library.view_book        —            True      True     editor → viewer (closure)  ok
alice   library.change_book      —            True      True     editor                     ok
alice   library.delete_book      —            False     False    no librarian               ok
bob     library.view_book        —            True      True     viewer (global)            ok
bob     library.change_book      —            False     False    no global editor           ok
bob     library.change_book      Dune         True      True     editor scoped to Dune      ok
bob     library.change_book      Hyperion     False     False    scope mismatch             ok
carol   library.add_book         —            True      True     librarian (if unexpired)   ok
carol   library.delete_book      —            True      True     librarian (if unexpired)   ok
dave    library.archive_book     —            True      True     archiver — custom perm     ok
dave    library.view_book        —            False     False    archiver is a separate root ok
admin   library.archive_book     —            True      True     is_superuser short-circuit ok
```

And the single SQL statement (`check_perm bob library.change_book --book Dune --sql`) that answers every check — regardless of hierarchy depth:

```sql
SELECT 1
FROM   rbac_role
JOIN   rbac_roleancestry   ON rbac_role.id = rbac_roleancestry.ancestor_id
JOIN   rbac_role_permissions ON rbac_role.id = rbac_role_permissions.role_id
JOIN   auth_permission     ON rbac_role_permissions.permission_id = auth_permission.id
JOIN   django_content_type ON auth_permission.content_type_id = django_content_type.id
WHERE  rbac_roleancestry.descendant_id IN (
           SELECT role_id FROM rbac_userrole
           WHERE  user_id = :bob
             AND  (expires_at IS NULL OR expires_at > NOW())
             AND  (content_type_id IS NULL OR (content_type_id = :book_ct AND object_id = :dune_pk))
       )
  AND  auth_permission.codename = 'change_book'
  AND  django_content_type.app_label = 'library'
LIMIT 1;
```

`demo_jit` pokes `carol`'s assignment to `expires_at = now() + 3s`, then polls `has_perm` every second. You watch `True, True, True, False, False` — the same query, driven purely by the `expires_at` column.

Key files:

- `rbac/models.py` — `Role`, `RoleAncestry`, `UserRole`
- `rbac/backends.py` — `ModelBackendNoAuthz` + `RBACBackend`
- `rbac/closure.py` + `rbac/signals.py` — closure rebuilder, wired to `post_save`/`post_delete`
- `library/models.py` — `Book` with custom `copy_book` / `archive_book` perms
- `rbac/management/commands/` — `seed_data`, `show_rbac`, `demo_checks`, `check_perm`, `demo_jit`

## Key Takeaways

- **Django's authz half is pluggable — trivially so.** Subclass `ModelBackend`, have all the `_permissions` / `has_perm` methods return empty/`False`, keep it in the chain for authentication. Your RBAC backend becomes the single source of truth.
- **Hierarchy + live permission checks = closure table.** Without the cache you're walking the tree on every request. With it, a check is one query regardless of depth. authentik does this with a Postgres MV + `pgtrigger`; a plain Django model updated by signals gets you the same semantics on SQLite.
- **Object-level scoping is a generic FK on the assignment, not a whole new permission model.** Same `Permission` row, same role, different `UserRole.scope`.
- **Just-in-time is literally one column.** `expires_at` on the assignment + `Q(expires_at__isnull=True) | Q(expires_at__gt=now())` in the query. No cron job, no revocation workflow.
- **Custom permissions don't need custom plumbing.** `Meta.permissions = [(...)]` gives you a `Permission` row. Your RBAC tables reference `auth.Permission` — they don't care whether the permission is `change_book` or `approve_merger`.

## Q&A Highlights

- **Q: In the backend chain, if `ModelBackend` comes first and returns `True` for model-level perms, doesn't it short-circuit before Guardian/RBAC is even consulted?**
  A: Close. `ModelBackend.has_perm` returns `True` only when the perm is actually granted to the user or a group; otherwise it returns `False`, and Django *continues the chain* (any backend returning `True` wins; `False` is not a veto). That's fine for adding object-level perms via Guardian, but not for a *replacement* strategy. You need the authz methods to be inert — hence `ModelBackendNoAuthz`.
- **Q: So you're not using Guardian at all?**
  A: We left its object-permission concept (generic FK, object-scoped perm) and replaced the backend + tables. authentik's real repo is exactly this: a vendored fork of `django-guardian` (`packages/ak-guardian`) with first-class `Role`, plus `ModelBackendNoAuthz` in front so Django's own authz can't leak through.

## Links

- authentik (speaker's company, open source): <https://github.com/goauthentik/authentik>
- authentik's forked `ak-guardian` with Role support: <https://github.com/goauthentik/authentik/tree/main/packages/ak-guardian>
- authentik's group hierarchy + ancestry MV (`GroupParentageNode` / `GroupAncestryNode`): <https://github.com/goauthentik/authentik/blob/main/authentik/core/models.py>
- `ModelBackendNoAuthz`: <https://github.com/goauthentik/authentik/blob/main/authentik/core/auth.py>
- Django auth backends: <https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#specifying-authentication-backends>
- Django custom permissions: <https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#custom-permissions>
- django-guardian: <https://django-guardian.readthedocs.io/>
- django-pgtrigger (for MV refresh on write): <https://django-pgtrigger.readthedocs.io/>

---
*Summarized at DjangoCon Europe 2026*

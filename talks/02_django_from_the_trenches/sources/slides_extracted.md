# Slides Extracted from Photos

Speaker: Haki Benita
Talk: Django from the Trenches (PostgreSQL indexing & optimization)
Context: URL shortener app (ShortUrl model) as running example

---

## Slide 1 — Debugging SQL

- Execute the query and get the execution plan and timing
- Shows `EXPLAIN ANALYZE` output on a query
- Code: `print(ShortUrl.objects.filter(...).explain(analyze=True))`
- Note: `explain()` with `analyze=True` available in Django

---

## Slide 2 — Lookup by Key

Include the URL in the index:

```python
class ShortUrl(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['key'],
                name='%(app_label)s_%(class)s_key_uk',
                include=['url'],
            ),
        ]
```

"But don't index it!" — use `include` to store the URL in the index without indexing it (covering index).

---

## Slide 3 — Finding URLs by Domain

Find all short URLs linking to a specific domain:

```python
def find_by_domain(domain: str) -> QuerySet[ShortUrl]:
    return ShortUrl.objects.alias(domain=Func(
        F('url'),
        function='SUBSTRING',
        template="%(function)s(%(expressions)s from '.*://([^/]*)')",
    )).filter(domain=domain)
```

Uses regex to extract domain from URLs.
Reference: https://hakibenita.com/sql-for-data-analysis

---

## Slide 4 — Alias vs. Annotate

What's the difference?
- `annotate` — adds the computed value to the SELECT list
- `alias` — does NOT add to the SELECT list, only available for filtering

Alias is not included in select list (more efficient when you only need it for WHERE).

---

## Slide 5 — Function Based Index

Index an expression:

```python
from django.db.models import F, Func

class ShortUrl(models.Model):
    class Meta:
        indexes = [
            models.Index(
                name='%(app_label)s_%(class)s_domain_fix',
                Func(
                    F('url'),
                    function='SUBSTRING',
                    template="%(function)s(%(expressions)s from '.*://([^/]*)')",
                ),
            ),
        ]
```

---

## Slide 6 — Function Based Index Result

After adding the function-based index:
- Query took 51ms to complete
- **x60 times faster!**
- Shows `EXPLAIN ANALYZE` using Bitmap Index Scan on the function-based index

---

## Slide 7 — Find Unused Keys

Remove the full index on `hits`:

```python
class ShortUrl(models.Model):
    # Before:
    # hits = models.PositiveIntegerField(db_index=True)

    # After:
    hits = models.PositiveIntegerField()
```

---

## Slide 8 — Find Unused Keys (Partial Index)

Add a *partial* B-Tree index on short URLs with zero hits:

```python
from django.db import models
from django.db.models import Q

class ShortUrl(models.Model):
    class Meta:
        indexes = [
            models.Index(
                fields=['id'],
                condition=Q(hits=0),
                name='shorturl_unused_part_ix',
            ),
        ]

    hits = models.PositiveIntegerField()
```

---

## Slide 9 — Partial Indexes

- Produce smaller indexes
- Limited to queries using the indexed rows
- Nullable columns are great candidates
- Use when possible

Reference: "The Unexpected Find That Freed 20GB of Index Space"

---

## Slide 10 — Reverse Lookup (Hash Index)

Add a Hash index on `url`:

```python
from django.contrib.postgres.indexes import HashIndex

class ShortUrl(models.Model):
    class Meta:
        indexes = [
            HashIndex(
                fields=['url'],
                name='shorturl_url_hix',
            ),
        ]
```

Add `django.contrib.postgres` to `settings.INSTALLED_APPS`.

---

## Slide 11 — Hash Index (Chart)

Hash vs. B-Tree Index Size chart:
- Hash indexes grow much slower than B-Tree as rows increase
- Both for `key` and `url` fields, Hash is significantly smaller

---

## Slide 12 — Hash Index (Properties)

- Ideal when values are *almost unique*
- Not affected by the size of the values
- Can be smaller and faster than a B-Tree
- Was discouraged prior to PostgreSQL 10, but no more!

Reference: "Re-Introducing Hash Indexes in PostgreSQL"

---

## Slide 13 — Enforcing Uniqueness with Hash

```python
from django.contrib.postgres.constraints import ExclusionConstraint
from django.db.models import F

class ShortUrl(models.Model):
    class Meta:
        constraints = [
            ExclusionConstraint(
                index_type='hash',
                expressions=[(F('url'), '=')],
                name='%(app_label)s_%(class)s_url_unique_hash',
            ),
        ]
```

Exclusion with hash is expected in Django 6.1.
Reference: "Unconventional PostgreSQL Optimizations"

---

## Slide 14 — Range Search

Find short URLs created in a date range:

```python
ShortUrl.objects.filter(
    created_at__gte=datetime(..., tzinfo=UTC),
    created_at__lt=datetime(..., tzinfo=UTC),
)
```

- Creation date set by the application when a row is added
- Creation date is naturally incrementing (correlation ~1)

---

## Slide 15 — Range Search (B-Tree size)

B-Tree index on `created_at` is ~2208 kB (shown via `\di+` in psql).

---

## Slide 16 — Block Range Index (BRIN) intro

"Keep range of values within a number of adjacent pages"

---

## Slide 17 — BRIN Index (How it works)

1. You have values in a column, each is a single page: [1] [2] [3] [5] [6] [7] [8] [9]
2. Divide the table into ranges of 3 adjacent pages: [1,2,3] [4,5,6] [7,8,9]
3. For each range, keep only the min and max values: [1-3] [4-6] [7-9]

---

## Slide 18 — Range Search (BRIN in Django)

```python
class ShortUrl(models.Model):
    class Meta:
        indexes = [
            BrinIndex(
                fields=('created_at',),
                pages_per_range=4,
                name='shorturl_created_at_bix',
            ),
        ]
```

---

## Slide 19 — Range Search (BRIN explain)

Shows `EXPLAIN ANALYZE` output using Bitmap Index Scan on BRIN index.
"Heap Index Scan on shorturl_created_at_bix"

---

## Slide 20 — Range Search (BRIN size)

```
shorturl_created_at_ix  | index | shorturl | 2208 kB
shorturl_created_at_bix | index | shorturl |   64 kB
```

BRIN is very small! (64 kB vs 2208 kB for B-Tree)

---

## Slide 21 — Range Search (BRIN vs B-Tree comparison)

| Access method      | Index Size | Timing    |
|--------------------|-----------|-----------|
| Full table scan    | -         | 19.003 ms |
| B-Tree index scan  | 2208 kB   | 2.178 ms  |
| BRIN index scan    | 64 kB     | 5.207 ms  |

- B-Tree is faster
- BRIN is smaller
- Trade-off: speed vs disk space

---

## Slide 22 — BRIN Index (When it fails)

Search for value 5 with ranges [2-9], [1-7], [3-8]:
- All ranges say "Might be here"
- "The index is useless!" when data is not naturally sorted

---

## Slide 23 — BRIN Index: Pages per range

```python
BrinIndex(
    fields=('created_at',),
    pages_per_range=128,  # adjustable
    name='shorturl_created_at_bix',
)
```

- Low `pages_per_range` → more accurate, bigger size
- High `pages_per_range` → less accurate, smaller size
- Default is 128, minimum is 2

---

## Slide 24 — BRIN Index (When to use)

- Ideal when data is naturally sorted on disk
  - Find columns with high correlation in `pg_stats.correlation`
  - Auto incrementing columns (timestamps etc.)
- Ideal for tables that don't update frequently
- Adjust `pages_per_range` to find ideal range size

---

## Slide 25 — BRIN Index: Built-in Operator Classes

- `minmax` (default) — keeps min and max values. Useful for high correlation data
- `minmax-multi` (New in PostgreSQL 14) — keeps multiple min and max values. Useful for high correlation data with outliers
- `bloom` (New in PostgreSQL 14) — keeps a bloom index for values in range. Useful for data with low correlation

---

## Slide 26 — When to Use Indexes?

- Indexes can make queries faster
- Indexes make inserts and updates slower
- Indexes can take up a lot of disk space
- Using an index is not always best!

**More ≠ Merrier**

---

## Slide 27 — Recap

- **Index types and features**
  - Inclusive, partial and function based B-Tree index
  - Hash index
  - Block Range (BRIN) index
- **How to evaluate performance**
  - Not just about speed!
- **Tools of the trade**
  - EXPLAIN ANALYZE and timing
  - Establish a baseline → optimize → repeat

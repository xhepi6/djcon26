# Django from the Trenches: Advanced Indexing in Django & PostgreSQL

> **Speaker:** Haki Benita — Software consultant, 10+ years with Django & PostgreSQL, built products serving millions of users
> **Event:** DjangoCon Europe 2026 (Greece)

## What is this about?

Your Django app works fine until it doesn't. Tables grow, queries slow down, indexes eat disk space. This talk shows you **which PostgreSQL index to use and when**, all through Django's ORM. The running example is a URL shortener.

## The Problem

- Default B-Tree indexes aren't always the best choice
- `db_index=True` on every field wastes disk space
- Nullable foreign keys create bloated indexes (nulls are indexed too)
- Sequential scans on expressions (like regex) are slow and repeated on every query
- More indexes ≠ better performance — they slow down inserts/updates and eat disk

## The Toolbox

### Debugging SQL in Django

Before optimizing, you need to see what's happening:

```python
# See the SQL
print(ShortUrl.objects.filter(key="abc").query)

# See the execution plan (without running)
print(ShortUrl.objects.filter(key="abc").explain())

# See the plan AND run it (get real timing)
print(ShortUrl.objects.filter(key="abc").explain(analyze=True))
```

## Index Types & Techniques

### 1. Covering Index (include)

**Problem:** Looking up a URL by key reads the index, then goes to the table to fetch the URL. That's 3 disk reads.

**Solution:** Store the URL *inside* the index leaf block. Now it's 2 reads (index-only scan).

```python
class ShortUrl(models.Model):
    key = models.CharField(max_length=20, unique=True)
    url = models.URLField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['key'],
                name='%(app_label)s_%(class)s_key_uk',
                include=['url'],  # stored in index, not indexed
            ),
        ]
```

**When to use:** Hot queries that only need a few columns. Beware: it doubles storage for the included field.

---

### 2. alias() vs annotate()

**`annotate()`** adds the computed value to both SELECT and WHERE.
**`alias()`** adds it only to WHERE — more efficient when you just need to filter.

```python
# Bad — SUBSTRING runs twice in the SQL (SELECT + WHERE)
ShortUrl.objects.annotate(
    domain=Func(F('url'), function='SUBSTRING',
        template="%(function)s(%(expressions)s from '.*://([^/]*)')"),
).filter(domain='example.com')

# Good — SUBSTRING only in WHERE
ShortUrl.objects.alias(
    domain=Func(F('url'), function='SUBSTRING',
        template="%(function)s(%(expressions)s from '.*://([^/]*)')"),
).filter(domain='example.com')
```

---

### 3. Function-Based Index (FBI)

**Problem:** Finding URLs by domain requires a regex on every row, every time. 3 seconds for a full table scan.

**Solution:** Index the *result* of the expression. The regex runs once when data is inserted, not on every query.

```python
from django.db.models import F, Func

class ShortUrl(models.Model):
    class Meta:
        indexes = [
            models.Index(
                Func(
                    F('url'),
                    function='SUBSTRING',
                    template="%(function)s(%(expressions)s from '.*://([^/]*)')",
                ),
                name='%(app_label)s_%(class)s_domain_fix',
            ),
        ]
```

**Result:** 3 seconds → 51ms (x60 faster)

**Important:** The expression in your query must be *exactly* the same as in the index. PostgreSQL won't match equivalent-but-different expressions.

**Practical tip:** In most cases, just add a real field (e.g. `domain = models.CharField(...)`) and populate it on save. Function-based indexes are better when you can't change the model.

---

### 4. Partial Index

**Problem:** You have `hits = models.PositiveIntegerField(db_index=True)`. The index covers ALL rows (7 MB), but you only query `hits=0`.

**Solution:** Index only the rows you care about.

```python
from django.db.models import Q

class ShortUrl(models.Model):
    hits = models.PositiveIntegerField()  # no db_index!

    class Meta:
        indexes = [
            models.Index(
                fields=['id'],
                condition=Q(hits=0),
                name='shorturl_unused_part_ix',
            ),
        ]
```

**Result:** 7 MB → 88 KB

**Best candidates for partial indexes:**
- Nullable foreign keys — set `db_index=False` on the FK, create a partial index with `condition=Q(field__isnull=False)`
- Status fields — index only active/pending rows
- Boolean flags — index only `True` (or `False`)

**Real-world win:** One team freed 20GB of index space by replacing full indexes on nullable FKs with partial indexes.

---

### 5. Hash Index

**Problem:** B-Tree index on `url` is 47 MB because URLs are long and B-Tree stores the full value in leaf blocks.

**Solution:** Hash index stores hash values, not actual values. Size doesn't depend on value length.

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

**Result:** 47 MB → 32 MB, and faster lookups

**Add to settings:**
```python
INSTALLED_APPS = [
    ...
    'django.contrib.postgres',
]
```

**When to use Hash:**
- Values are *almost unique* (few duplicates)
- You only do equality lookups (`=`), never range queries (`<`, `>`, `BETWEEN`)
- Large values (long strings, URLs) — hash size is constant regardless of value size

**Limitations:** No range queries, no ordering, no multi-column, can't be used for FK references.

**Enforcing uniqueness with Hash** (expected in Django 6.1):

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

---

### 6. BRIN Index (Block Range Index)

**Problem:** B-Tree index on `created_at` is 2208 KB. Works great but takes space, especially on big tables.

**How BRIN works:**
1. Divide the table into groups of adjacent pages
2. For each group, store only the min and max values
3. To search, check which groups *might* contain your value

```
Pages:  [1,2,3]  [4,5,6]  [7,8,9]
BRIN:   [1-3]    [4-6]    [7-9]
```

**In Django:**

```python
from django.contrib.postgres.indexes import BrinIndex

class ShortUrl(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            BrinIndex(
                fields=('created_at',),
                pages_per_range=4,
                name='shorturl_created_at_bix',
            ),
        ]
```

**Result comparison:**

| Method | Index Size | Query Time |
|--------|-----------|------------|
| Full table scan | — | 19.0 ms |
| B-Tree | 2208 kB | 2.2 ms |
| BRIN | 64 kB | 5.2 ms |

**Trade-off:** B-Tree is faster. BRIN is **35x smaller**. Choose based on what matters more.

**`pages_per_range` tuning:**
- Low value (e.g. 2) → more accurate, bigger index
- High value (e.g. 128, the default) → less accurate, smaller index

**When BRIN works:**
- Data is naturally sorted on disk (timestamps, auto-incrementing IDs)
- Check with `pg_stats.correlation` — values close to 1.0 or -1.0 are good
- Tables that don't update frequently (updates scramble disk order)

**When BRIN fails:** If data is randomly ordered, every range says "might be here" and the index is useless.

**Operator classes (PostgreSQL 14+):**
- `minmax` (default) — min/max per range, good for high correlation
- `minmax-multi` — multiple min/max, handles outliers
- `bloom` — bloom filter per range, works with low correlation

---

## When to Use Indexes?

- Indexes make reads faster but writes slower
- Indexes take disk space (doubled data)
- More indexes ≠ better
- Always measure: `EXPLAIN ANALYZE` before and after

**Workflow:** Establish baseline → add index → measure → compare

## Experiment

The `experiment/` folder has a runnable Django project with all index types. **Requires PostgreSQL.**

```bash
cd experiment
docker compose up -d                # starts PostgreSQL on port 55434
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data          # 10k rows (or: seed_data 100000)

# See all index sizes and query plans
python manage.py debug_indexes
```

| Command | What it shows |
|---------|---------------|
| `python manage.py debug_indexes` | Index sizes + EXPLAIN ANALYZE for every query pattern |
| `python manage.py shell` | Import from `shortener.queries` and experiment |
| `python manage.py runserver` | Hit `/r/<key>/`, `/by-domain/example.com/`, `/unused/` |

Key files to explore:
- `shortener/models.py` — all 5 index types in one model
- `shortener/queries.py` — one function per index pattern, with `explain()` helper
- `shortener/management/commands/debug_indexes.py` — compare all indexes at once

**Experiment ideas:**
- Comment out indexes one by one, re-migrate, run `debug_indexes` to see the difference
- Try `seed_data 500000` and compare index sizes
- Uncomment the LOGGING block in `settings.py` to see all SQL in the console
- Change `pages_per_range` on the BRIN index and compare accuracy vs size

## Key Takeaways

- **`explain(analyze=True)`** is your best friend — use it before and after every change
- **Covering indexes** avoid table lookups but double storage for included fields
- **`alias()` > `annotate()`** when you only need the value for filtering
- **Partial indexes** can save 99% of index space — check your nullable FKs
- **Hash indexes** are smaller and faster for equality lookups on large values
- **BRIN indexes** are tiny for naturally ordered data (timestamps) — trade speed for space
- **Don't over-index** — every index slows down writes and costs disk space

## Q&A Highlights

- **Partial index on nullable FK** is the single biggest quick win — Django auto-creates full B-Tree indexes on every FK, even nullable ones. Set `db_index=False` and add a partial index
- **Partial index condition must match query exactly** — `Q(hits=0)` index only works for `filter(hits=0)`, not `filter(hits__gt=0)`
- **Function-based index vs real field** — in most cases, just add a column. FBI is for when you can't modify the model or need backward compatibility
- **Hash index bucket splits** cause the step-like growth pattern in the size chart — buckets double when full

## Links

- Speaker's blog: https://hakibenita.com
- Hash indexes: https://hakibenita.com/postgresql-hash-index
- Partial indexes (20GB saved): https://hakibenita.com/postgresql-unused-index-size
- PostgreSQL optimizations: https://hakibenita.com/postgresql-unconventional-optimizations
- Django 3.2 features (covering, alias, FBI): https://hakibenita.com/django-32-exciting-features
- Django FK indexes: https://hakibenita.com/django-foreign-keys

---
*Summarized at DjangoCon Europe 2026*

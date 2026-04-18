# Digitising Historical Caving Data with Python and Django

> **Speaker:** Andrew Northall — author of [caves.app](https://github.com/anorthall/caves.app), volunteer digitiser for the National Speleological Society.
> **Event:** DjangoCon Europe 2026

## What is this about?

Sixty years of caving-incident reports — thousands of pages — sit trapped in scanned PDFs that no one can search. Andrew built a pipeline that takes those PDFs and turns them into a structured, queryable Django database: OCR with Docling, LLMs for layout-aware extraction and cleanup, and a Django-native architecture for running (and re-running) the messy processing steps in between. Of the 2,700+ incidents extracted, ~12 hours of compute replaced five years of volunteer effort. This talk is about the Django-shaped parts that made the pipeline tractable.

## The Problem

- NSS has published *American Caving Accidents* yearly since 1967 — authoritative, freely-available PDFs, **but unindexed**
- Scans vary: half-typewritten, half-photocopied, multi-column layouts, figure captions threaded through prose
- OCR struggles: degraded characters, column ordering, hyphenated line breaks
- Dates in the source: `"1971"`, `"August 1985"`, `"Autumn 1996"`, `"15 March 2024"` — no `DateField` captures all four
- Locations likewise: sometimes `"Arizona"`, sometimes `"Carlsbad Caverns, NM, USA"` — variable precision
- Manual digitisation with volunteers: 3+ years of effort produced **200 records**, and got slower over time

## The Solution

A five-stage pipeline, Django at the centre:

1. **OCR** — [Docling](https://github.com/docling-project/docling) (IBM Research). Gives structured text with coordinates, column ordering, table/figure detection. Effectively skipped by this demo; the talk's takeaway is "use a good OCR tool, don't build your own".
2. **Segmentation** — an LLM splits the OCR blob into one-incident-per-text-file. Small context per call; iterative ("is this a complete incident? → yes → next").
3. **Rewrite / cleanup** — LLM fixes OCR artefacts, punctuation, line-break hyphenation. *Must not hallucinate content.*
4. **Self-check** — a **second LLM pass** grades the first. If output looks bad, record the step as **FAILED** and move on — don't crash, don't silently accept.
5. **Structuring** — classify severity, parse location, parse date, store in Postgres.

The three **Django-shaped** patterns that make this work and that this experiment focuses on:

### 1. Pluggable processing-step architecture

Every step is an `Operation` subclass with a tiny contract: `should_run(incident)` + `run(incident)`. A class-level `requires = [OtherOp]` declares prerequisites. A module-level `@register` adds the step to the pipeline. The runner (a management command) iterates operations × incidents, records an `OperationRun` row per attempt, and respects dependencies.

New step = new file. No central list, no if-ladder.

### 2. Custom `FuzzyDate` model field

`FuzzyDate` is a dataclass with `year`, `precision` (`year` / `season` / `month` / `day`), and optional `month`/`day`/`season`. The `FuzzyDateField` serialises to a compact, lexicographically-sortable string: `"1996-09-01:season:autumn"`. The three lifecycle hooks — `to_python` / `from_db_value` / `get_prep_value` — are the whole custom-field pattern in ~30 lines.

Andrew's note: almost no off-the-shelf library does this, because "Autumn 1996" isn't a valid anything in stdlib datetime.

### 3. Tree-structured locations

Using `django-treebeard`'s `MP_Node` (Materialized Path). Incidents attach at whatever depth the source provides — `Arizona` is a state-level node, `Carlsbad Caverns` is a region-level node under `New Mexico` under `USA`. Rolling up "how many incidents in the USA?" is a single `get_descendants()` query; flat (country/state/region/cave) columns can't do this without a lot of null-checking and custom aggregation.

## How to Use It

### Install

```bash
pip install "Django>=5.2" "psycopg[binary]" "django-treebeard"
```

### 1. The custom field

```python
# incidents/fields.py
@dataclass(frozen=True)
class FuzzyDate:
    year: int
    precision: Precision       # year / season / month / day
    month: int | None = None
    day: int | None = None
    season: str | None = None

    def to_storage(self) -> str:
        mm, dd = self.month or 1, self.day or 1
        prefix = f"{self.year:04d}-{mm:02d}-{dd:02d}"
        if self.precision is Precision.SEASON:
            return f"{prefix}:season:{self.season}"
        return f"{prefix}:{self.precision}"


class FuzzyDateField(models.CharField):
    def from_db_value(self, value, expression, connection):
        return None if value is None else FuzzyDate.from_storage(value)

    def to_python(self, value):
        if value is None or isinstance(value, FuzzyDate):
            return value
        return FuzzyDate.from_storage(value)

    def get_prep_value(self, value):
        return None if value is None else value.to_storage()
```

### 2. The tree

```python
# incidents/models.py
from treebeard.mp_tree import MP_Node

class Location(MP_Node):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LocationLevel.choices)
    node_order_by = ["name"]

# Creating the tree:
usa = Location.add_root(name="USA", level="country")
nm = usa.add_child(name="New Mexico", level="state")
nm.add_child(name="Carlsbad Caverns", level="region")

# All incidents anywhere in the USA:
Incident.objects.filter(location__in=usa.get_descendants())
```

### 3. The pluggable step pattern

```python
# incidents/operations/base.py
_REGISTRY: list[type["Operation"]] = []

def register(op_cls):
    _REGISTRY.append(op_cls)
    return op_cls


class Operation:
    requires: list[type["Operation"]] = []

    def should_run(self, incident) -> bool:
        return True

    def run(self, incident) -> None:
        raise NotImplementedError


# incidents/operations/fake_llm_critic.py
@register
class FakeLLMCritic(Operation):
    requires = [FakeLLMRewrite]          # won't run until rewrite succeeds

    def run(self, incident):
        if re.search(r"\?{2,}", incident.cleaned_text):
            raise ValueError("unresolved OCR glyph")   # → recorded as FAILED
```

### 4. The runner

```python
for incident in incidents:
    for op_cls in get_registry():
        if _already_succeeded(incident, op_cls):
            continue
        if not _prereqs_satisfied(incident, op_cls):
            continue                      # blocked — try again next pass
        op = op_cls()
        if not op.should_run(incident):
            _record(incident, op_cls, SKIPPED); continue
        try:
            op.run(incident)
        except Exception as exc:
            _record(incident, op_cls, FAILED, str(exc))
        else:
            _record(incident, op_cls, SUCCESS)
```

## Experiment

The `experiment/` folder has a runnable Django project with 8 hand-written fake incident records exercising every date format, every tree depth, and a deliberately-broken text that the self-check pass flags as `FAILED`.

```bash
cd experiment

# Postgres in docker (exposes 55433 on the host — no collision with local PG or talk 06)
docker compose up -d

pip install -r requirements.txt
python manage.py migrate

python manage.py seed_raw             # 8 raw incidents, every date + location shape
python manage.py process              # run every operation against every incident
python manage.py show_pipeline        # dashboard: one row per incident, one column per op
python manage.py demo_fuzzy_date      # the custom field in isolation
python manage.py demo_tree            # Location tree with subtree incident counts
python manage.py process --rerun --op ClassifySeverity   # re-run a single step
python manage.py process --retry-failed                  # re-attempt FAILED rows
```

What the `show_pipeline` output looks like after `process`:

```
 id  ParseDat  ParseLoc  FakeLLMR  FakeLLMC  Classify   severity   when              where
------------------------------------------------------------------------------------------------------------------------
  1         ✓         ✓         ✓         ✓         ✓   injury     15 March 2024     USA → New Mexico → Carlsbad Caverns
  2         ✓         ✓         ✓         ✓         ✓   rescue     August 1985       USA → Kentucky → Mammoth Cave
  3         ✓         ✓         ✓         ✓         ✓   rescue     Autumn 1996       USA → Florida → Ginnie Springs
  4         ✓         ✓         ✓         ✓         ✓   minor      1971              USA → Arizona
  5         ✓         ✓         ✓         ✓         ✓   fatal      4 October 1982    USA → Georgia → Ellison's Cave
  …
  8         ✓         ✓         ✓         ✗         ✓   injury     Spring 2008       USA → Unknown

Failures (what the critic caught):
  #8   FakeLLMCritic        cleaned_text still contains: \?{2,}
```

Row 4 attaches at **state** level (`Arizona`), rows 1-3 attach at **region** level — the tree makes that natural. Row 8's critic caught an unresolved `???` artefact in the cleaned text and recorded **FAILED** without crashing the pipeline.

Key files:

- `incidents/fields.py` — `FuzzyDate` dataclass + `FuzzyDateField`
- `incidents/models.py` — `Incident`, `Location(MP_Node)`, `OperationRun` with `unique_together` on `(incident, op)`
- `incidents/operations/base.py` — the `Operation` base class + `@register` + registry
- `incidents/operations/*.py` — five concrete steps, each tiny
- `incidents/management/commands/process.py` — the runner; handles deps, skipping, rerun flags

## Key Takeaways

- **Make it pluggable.** Operations as classes + a registry means new steps are drop-in, and you get rerun/status tracking for free. Andrew ran this 3,000+ times.
- **Have the LLM grade its own output.** A single pass always over-commits; a critic pass records *failure* without throwing away the first-pass text, so you can iterate on it.
- **Custom model fields are cheap.** `to_python` / `from_db_value` / `get_prep_value` — that's the whole contract. Reach for them when your domain has a type `DateField` + validators can't express.
- **Tree it when the depth varies.** `MP_Node` is a two-field model with built-in ancestor/descendant queries. If you're about to write nullable FKs for `country/state/region/cave`, use a tree instead.
- **OCR is a solved problem — for now.** Use Docling; don't write coordinate math yourself.

## Q&A Highlights

- **Why not put the whole document in a 1M-token context and extract everything in one call?** Tried it; doesn't work. The attention budget at that context length means the model misses incidents. Small chunks + iterate is more reliable.
- **Spatial data on the caves?** For a fixed-schema product you'd want PostGIS. For this dataset, a tree is enough — most source locations are fuzzy enough that a point-in-space would itself be a false precision.
- **What about duplicates?** Source PDFs re-publish older incidents in later annual reports. The production system uses sentence-transformer embeddings + cosine similarity > 0.8 to flag near-duplicates, then an LLM to confirm. Not included in this demo — scope.
- **Volunteer work wasn't wasted** — their manually-cleaned 200 incidents became the verification set for the LLM pipeline.

## Links

- caves.app (Andrew's project): <https://github.com/anorthall/caves.app>
- American Caving Accidents (the source PDFs): <https://caves.org/pub/aca/>
- Docling (OCR): <https://github.com/docling-project/docling>
- django-treebeard docs: <https://django-treebeard.readthedocs.io/>
- Django custom model fields: <https://docs.djangoproject.com/en/5.2/howto/custom-model-fields/>

---
*Summarized at DjangoCon Europe 2026*

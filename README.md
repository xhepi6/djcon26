# DjangoCon Europe 2026 - Talk Summaries

Practical, noise-free summaries of DjangoCon Europe 2026 talks. Each talk comes with a runnable Django project so you can experiment with the topic hands-on.

## What's in here

Each folder in `talks/` is one talk:

| # | Talk |
|---|------|
| 01 | [Static Islands in a Dynamic Sea](talks/01_static_islands_dynamic_sea) |
| 02 | [Django From the Trenches](talks/02_django_from_the_trenches) |
| 03 | [Reliable Django Signals](talks/03_reliable_django_signals) |
| 04 | [Django Forms in the Age of HTMX](talks/04_django_forms_in_the_age_of_htmx) |
| 05 | [Scaling the Database: Multiple Databases with Django](talks/05_scaling_the_database_using_multiple_databases_with_django) |
| 06 | [Partitioning Very Large Tables with Django and PostgreSQL](talks/06_partitioning_very_large_tables_with_django_and_postgresql) |
| 07 | [Digitising Historical Caving Data with Python and Django](talks/07_digitising_historical_caving_data_with_python_and_django) |
| 08 | [Role-Based Access Control in Django](talks/08_role_based_access_control_in_django) |
| 09 | [Where Did It All Begin](talks/09_where_did_it_all_begin) |
| 10 | [What's in Your Dependencies](talks/10_whats_in_your_dependencies) |
| 11 | [Is It Time for a Django Admin Rewrite?](talks/11_is_it_time_for_django_admin_rewrite) |

## Talk folder structure

```
talks/XX_talk_name/
  README.md              # summary (renders on GitHub)
  manage.py
  requirements.txt
  config/                # settings, urls
  <app>/                 # app scoped to the talk topic
  templates/             # test panel (if present)
```

Each talk is **self-contained** -- separate requirements, separate db, no shared monolith.

## How to run an experiment

Pick any talk and:

```bash
cd talks/XX_talk_name
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
docker compose up -d       # only if the talk has a docker-compose.yml
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Each talk has its own dependencies. If you're exploring multiple talks, **create a separate venv per talk** so packages don't clash.

Some talks require **PostgreSQL** (indexes, partitioning). Those include a `docker-compose.yml` that starts Postgres on a non-default port so it doesn't collide with other talks or a local install.

Some talks include a `/test/` page with an interactive test panel that explains each endpoint and lets you run them from the browser.

## How to contribute

### Building an experiment

- Keep it minimal -- only what's needed to demo the topic
- SQLite by default. PostgreSQL only when the topic requires it
- Pin minimum versions in `requirements.txt`
- Add comments pointing to what each piece demonstrates
- Include `seed_data` management command for demo data
- Add a `/test/` page if the talk benefits from interactive testing
- It should just work with the 4-command sequence above

### Writing style

- Simple words, short sentences
- Lead with "what it does"
- Code over prose
- No fluff

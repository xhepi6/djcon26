# DjangoCon Europe 2026 - Talk Summaries

Practical, noise-free summaries of DjangoCon Europe 2026 talks. Each talk comes with a runnable Django project so you can experiment with the topic hands-on.

Blog post: [DjangoCon Europe 2026 in Athens](https://xhepi.dev/logs/djangocon-europe-2026-athens)

## What's in here

Each folder in `talks/` is one talk:

| # | Talk | Post |
|---|------|------|
| 01 | [Static Islands in a Dynamic Sea](talks/01_static_islands_dynamic_sea) | [read](https://xhepi.dev/logs/static-islands-in-a-dynamic-sea) |
| 02 | [Django From the Trenches](talks/02_django_from_the_trenches) | [read](https://xhepi.dev/logs/advanced-indexing-in-django-and-postgresql) |
| 03 | [Reliable Django Signals](talks/03_reliable_django_signals) | [read](https://xhepi.dev/logs/reliable-django-signals) |
| 04 | [Django Forms in the Age of HTMX](talks/04_django_forms_in_the_age_of_htmx) | [read](https://xhepi.dev/logs/django-forms-in-the-age-of-htmx) |
| 05 | [Scaling the Database: Multiple Databases with Django](talks/05_scaling_the_database_using_multiple_databases_with_django) | [read](https://xhepi.dev/logs/scaling-with-multiple-databases-in-django) |
| 06 | [Partitioning Very Large Tables with Django and PostgreSQL](talks/06_partitioning_very_large_tables_with_django_and_postgresql) | [read](https://xhepi.dev/logs/partitioning-very-large-tables-with-django) |
| 07 | [Digitising Historical Caving Data with Python and Django](talks/07_digitising_historical_caving_data_with_python_and_django) | [read](https://xhepi.dev/logs/digitising-historical-data-with-django) |
| 08 | [Role-Based Access Control in Django](talks/08_role_based_access_control_in_django) | [read](https://xhepi.dev/logs/role-based-access-control-in-django) |
| 09 | [Where Did It All Begin](talks/09_where_did_it_all_begin) | [read](https://xhepi.dev/logs/django-transaction-primitives) |
| 10 | [What's in Your Dependencies](talks/10_whats_in_your_dependencies) | [read](https://xhepi.dev/logs/supply-chain-security-for-python) |
| 11 | [Is It Time for a Django Admin Rewrite?](talks/11_is_it_time_for_django_admin_rewrite) | [read](https://xhepi.dev/logs/is-it-time-for-a-django-admin-rewrite) |

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

## Presentation

The `presentation/` folder has a [reveal.js](https://revealjs.com/) slideshow covering all 11 talks. Open `presentation/presentation.html` in a browser. Built with the [revealjs skill](https://github.com/anthropics/claude-code-installed-skills/tree/main/revealjs) for Claude Code.
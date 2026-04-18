# DjangoCon Europe 2026 - Talk Summaries

Practical, noise-free summaries of DjangoCon Europe 2026 talks. Each talk comes with a runnable Django project so you can experiment with the topic hands-on.

## What's in here

Each folder in `talks/` is one talk:

| # | Talk | Summary | Experiment |
|---|------|---------|------------|
| 01 | Static Islands in a Dynamic Sea | done | done |
| 02 | Django From the Trenches | done | done |
| 03 | Reliable Django Signals | done | done |
| 04 | Django Forms in the Age of HTMX | done | done |
| 05 | Scaling the Database: Multiple Databases with Django | done | done |
| 06 | Partitioning Very Large Tables with Django and PostgreSQL | done | done |
| 07 | Digitising Historical Caving Data with Python and Django | done | done |
| 08 | Role-Based Access Control in Django | done | done |
| 09 | Where Did It All Begin | - | - |
| 10 | What's in Your Dependencies | - | - |

## Talk folder structure

```
talks/XX_talk_name/
  README.md              # summary (renders on GitHub)
  sources/               # raw materials (temporary, will be removed)
  experiment/            # runnable Django project
    manage.py
    requirements.txt
    config/              # settings, urls
    <app>/               # app scoped to the talk topic
```

Each talk is **self-contained** -- separate requirements, separate db, no shared monolith.

## How to run an experiment

Pick any talk and:

```bash
cd talks/XX_talk_name/experiment
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Most experiments include management commands for seeding demo data:

```bash
python manage.py seed_data
```

## How to contribute

### Writing a summary

1. Look at `talks/template.md` for the format
2. Read the `sources/intro.txt` for the talk description
3. Use `sources/slides_extracted.md` as primary content (if it exists)
4. Use `sources/transcription.txt` for extra context (Q&A, nuance) -- never quote it directly, it's noisy auto-generated text
5. Write the `README.md` following the template

### Building an experiment

- Keep it minimal -- only what's needed to demo the topic
- SQLite by default. PostgreSQL only when the topic requires it
- Pin minimum versions in `requirements.txt`
- Add comments pointing to what each piece demonstrates
- Include `seed_data` management command for demo data
- It should just work with the 3-command sequence above

### Writing style

- Simple words, short sentences
- Lead with "what it does"
- Code over prose
- No fluff

## Status

Work in progress. Talks 09 and 10 still need summaries and experiments.

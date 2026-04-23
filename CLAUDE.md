# DjangoCon Europe 2026 - Talk Summaries

## Project Purpose

Practical, noise-free summaries of DjangoCon Europe 2026 talks. Each talk includes a runnable Django project to experiment with the topic.

## Experiment Project Rules

- Minimal — only what's needed to demo the topic
- SQLite by default. PostgreSQL when the topic requires it (indexes, postgres-specific features)
- `requirements.txt` with pinned minimum versions
- Comments in code pointing to what each piece demonstrates
- Include management commands for seeding data and debugging (e.g. `seed_data`, `debug_indexes`)
- Should work with: `pip install -r requirements.txt && python manage.py migrate && python manage.py runserver`

## Writing Style

- Simple words, short sentences
- Lead with "what it does" not "the philosophical underpinnings"
- Code > prose whenever possible
- Only include Q&A points that add practical value
- No emojis unless the user asks

## Git Rules

- No Co-Authored-By lines in commits

# DjangoCon Europe 2026 - Talk Summaries

## Project Purpose

Practical, noise-free summaries of DjangoCon Europe 2026 talks. Each talk includes a runnable Django project to experiment with the topic.

## Talk Folder Structure

```
talks/XX_talk_name/
  README.md              # summary (renders on GitHub)
  sources/               # raw materials
    intro.txt            # conference website description (clean)
    transcription.txt    # auto-generated, noisy, DO NOT quote directly
    mentions.txt         # libraries, links mentioned (optional)
    photos/              # slide photos (optional)
    slides_extracted.md  # extracted slide content (generated from photos)
  experiment/            # runnable Django project
    manage.py
    requirements.txt
    config/              # settings, urls
    <app>/               # app scoped to the talk topic
```

Each talk is self-contained. Separate requirements, separate db, no shared monolith.

## Summarization Workflow

1. If `sources/photos/` exists: process slides FIRST into `sources/slides_extracted.md` (saves tokens)
2. Read `sources/intro.txt` for clean framing
3. Use `slides_extracted.md` as primary content (cleaner than transcription)
4. Extract extra signal from `sources/transcription.txt` — Q&A insights, context. Never quote directly
5. Delegate fetching real code from official repos/docs to a subagent (token efficient)
6. Write `README.md` using `talks/template.md`
7. Create `experiment/` with a minimal Django project that demonstrates the talk's topic

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

# Where Did It All Begin?

> **Speakers:** Charlie Denton (@meshy) & Sam Searles-Bryant (@samueljsb) — Developer Foundations team at Kraken Tech (Octopus Energy)
> **Event:** DjangoCon Europe 2026

## What is this about?

Django's `transaction.atomic()` was a huge step forward in 2013, but it conflates two different things: creating transactions and creating savepoints. You can't tell which one your code does just by reading it. `django-subatomic` splits `atomic` into explicit primitives so your code says what it means.

## The Problem

- **`atomic()` is ambiguous** — the same code creates a transaction OR a savepoint depending on whether it's already inside a transaction. You can't tell by reading it
- **Unnecessary savepoints everywhere** — nested `atomic()` blocks create savepoint/release queries even when you don't need partial rollback. At scale (Kraken: 16M lines of Python), this adds up
- **`on_commit` callbacks can lie** — code inside `atomic(durable=True)` looks safe, but if an outer `atomic()` wraps it, the commit can still be rolled back after your callback fires
- **No way to require a transaction** — there's no built-in "this code must run inside a transaction but shouldn't create one" primitive

## The History

| Version | Year | What changed |
|---------|------|-------------|
| Pre-0.95 | 2005 | No transaction control. Django commits after every `save()`/`delete()` |
| 0.95 | 2006 | `commit_on_success` context manager. First transaction support |
| 1.6 | 2013 | Autocommit by default. `atomic()` introduced. Savepoints for nesting |
| 3.2 | 2021 | `durable` parameter added to `atomic()` |
| Today | 2026 | `django-subatomic` splits atomic into explicit parts |

### The nesting problem (pre-1.6)

```python
# With commit_on_success, nesting was broken:
with commit_on_success():       # begins transaction
    Author.objects.create(...)
    with commit_on_success():   # COMMITS everything here (too early!)
        Book.objects.create(...)
    # outer commit does nothing — data already committed
    # if an error happens here, rollback is too late
```

### How atomic() fixed it (1.6+)

```python
with transaction.atomic():           # BEGIN
    Author.objects.create(...)
    with transaction.atomic():       # SAVEPOINT (not a new transaction)
        Book.objects.create(...)
    # RELEASE SAVEPOINT
# COMMIT
```

Better, but now every nested `atomic()` creates savepoint queries you probably don't need.

## The Solution: django-subatomic

Split `atomic()` into four primitives that say exactly what they do:

| Primitive | What it does | Creates SQL? |
|-----------|-------------|-------------|
| `transaction()` | Creates a transaction. Fails if already in one | BEGIN / COMMIT |
| `savepoint()` | Creates a savepoint. Fails if NOT in a transaction | SAVEPOINT / RELEASE |
| `transaction_required()` | Asserts a transaction exists. Creates nothing | No SQL |
| `durable()` | Asserts code runs outside any transaction | No SQL |

Plus `run_after_commit()` — like `on_commit` but raises if no transaction is open (no silent immediate execution).

## How to Use It

### Install

```bash
pip install django-subatomic
```

No `INSTALLED_APPS` entry needed. Just import and use.

### Basic usage

```python
from django_subatomic import db

# Explicit transaction boundary
with db.transaction():
    Account.objects.create(name="Alice", balance=1000)
    Account.objects.create(name="Bob", balance=500)
# COMMIT — both accounts created atomically
```

### Require a transaction without creating one

```python
@db.transaction_required
def transfer(from_acct, to_acct, amount):
    """Must be called inside a transaction. Won't create one."""
    from_acct.balance -= amount
    from_acct.save()
    to_acct.balance += amount
    to_acct.save()
```

This is used orders of magnitude more than `savepoint()` at Kraken. Most code needs atomicity guarantees but shouldn't define the transaction boundary.

### Savepoints for partial rollback

```python
with db.transaction():
    Account.objects.create(name="Alice", balance=1000)
    try:
        with db.savepoint():
            # risky operation — can be rolled back independently
            apply_signup_bonus(alice)
    except BonusError:
        pass  # savepoint rolled back, transaction continues
# COMMIT — Alice exists, bonus may or may not
```

### Durable side effects

```python
@db.durable
def send_welcome_email(email):
    """Guaranteed to run outside any transaction."""
    EmailService.send(email)
```

If called inside a transaction, it raises immediately. No more "email sent but data rolled back" bugs.

### After-commit callbacks

```python
from functools import partial

with db.transaction():
    user = User.objects.create(username="alice")
    db.run_after_commit(partial(send_welcome_email, user.email))
# Email sends only after successful COMMIT
```

Unlike Django's `on_commit`, `run_after_commit` raises if no transaction is open — prevents silent immediate execution.

### Gradual migration

`django-subatomic` works alongside existing `atomic()` blocks. You can migrate incrementally — start with new code, convert old code over time.

## Experiment

The `experiment/` folder has a runnable Django project that demonstrates the difference between `atomic()` and `django-subatomic`. Try it:

```bash
cd experiment
docker compose up -d                # starts PostgreSQL on port 55435
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
```

Then run the demos:

```bash
# Show how atomic() creates unnecessary savepoints
python manage.py demo_atomic

# Show how subatomic primitives give explicit control
python manage.py demo_subatomic
```

Key files to explore:
- `banking/models.py` — Account and TransferLog models
- `banking/services.py` — transfer logic using both approaches
- `banking/management/commands/demo_atomic.py` — shows atomic() behavior with SQL logging
- `banking/management/commands/demo_subatomic.py` — shows subatomic behavior with SQL logging

## Key Takeaways

- **`atomic()` was a huge improvement** over `commit_on_success`, but it hides whether you're getting a transaction or a savepoint
- **Most code needs `transaction_required`**, not `atomic()` — you want atomicity guarantees without creating transaction boundaries everywhere
- **Unnecessary savepoints cost real queries** — at scale, the extra SQL adds up
- **`django-subatomic` is production-tested** — running across 100+ environments at Kraken Tech
- **Migrate incrementally** — subatomic works alongside `atomic()`, no big-bang rewrite needed

## Q&A Highlights

- **Getting into Django core?** Speakers have started writing a proposal but have unsolved problems (namespace clashes, deferred constraints in tests)
- **Works with existing `atomic()`?** Yes, if `atomic()` is the outermost block, everything works. You just don't get the extra guardrails for that block
- **Database support?** Tested against PostgreSQL. No DB-specific SQL used, so it should work with all backends. Plan to expand test matrix
- **Nested savepoints in PostgreSQL** can cause performance issues — Postgres switches from memory to disk at depth, which is what initially pushed Kraken down this path

## Links

- django-subatomic: https://github.com/kraken-tech/django-subatomic
- PyPI: https://pypi.org/project/django-subatomic/
- Docs: https://kraken-tech.github.io/django-subatomic/
- Aymeric Augustin's 2013 talk (atomic() origin): https://www.youtube.com/watch?v=pqAsIm9_Eg4
- David Seddon's blog "The trouble with transaction.atomic": https://seddonym.me/2020/11/19/trouble-atomic/
- Kraken Tech: https://kraken.tech/

---
*Summarized at DjangoCon Europe 2026*

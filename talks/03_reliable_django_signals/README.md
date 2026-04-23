# Reliable Django Signals

> **Speaker:** Haki Benita — Django and PostgreSQL specialist, author of hakibenita.com
> **Event:** DjangoCon Europe 2026 (Greece)

## What is this about?

Django signals are great for decoupling modules, but they're unreliable. Receiver failures, side effects inside transactions, and no delivery guarantees make them risky for critical workflows. This talk shows how to make signals reliable using Django 6's tasks framework and a database queue — the transactional outbox pattern.

## The Problem

- **Circular dependencies** — order creates payment, but payment needs to notify order back. Direct imports create cycles
- **Receiver failures crash the sender** — `signal.send()` propagates exceptions from receivers back to the sender
- **`send_robust()` isn't enough** — it swallows exceptions, but receivers still run inside the sender's transaction
- **Long-running receivers block the transaction** — a slow email send holds the database lock open
- **Receiver database errors abort the sender's transaction** — one bad receiver rolls back everything
- **Side effects can't be rolled back** — if a receiver sends an SMS then the transaction rolls back, the user gets a message for something that didn't happen
- **Moving the signal outside the transaction creates a gap** — if the process crashes after commit but before the signal fires, receivers never execute. The payment succeeds but the order stays pending forever

## The Solution

Use a **database queue** to enqueue signal receivers as tasks **inside** the sender's transaction. The tasks are committed atomically with the data change. A separate worker process picks them up after commit.

This is the **transactional outbox pattern**:

1. Signal is sent inside `transaction.atomic()`
2. Instead of executing receivers immediately, a task is written to a database table (same transaction)
3. If the transaction rolls back, the task rows disappear too
4. If it commits, a background worker picks up and executes each receiver
5. Failed receivers can be retried by the worker

This gives you: decoupling + at-least-once delivery + fault tolerance.

## How to Use It

### Install

```bash
pip install "Django>=6"
pip install django-tasks django-tasks-db
```

### 1. Configure the tasks backend

```python
# settings.py
INSTALLED_APPS = [
    # ...
    'django_tasks',
    'django_tasks_db',
]

TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.DatabaseBackend",
        "ENQUEUE_ON_COMMIT": False,  # we enqueue inside the transaction intentionally
    }
}
```

Run migrations and start the worker:

```bash
python manage.py migrate
python manage.py db_worker
```

### 2. Create a ReliableSignal class

```python
from django.dispatch import Signal as DjangoSignal
from django.dispatch.dispatcher import NO_RECEIVERS

class Signal(DjangoSignal):
    def send_reliable(self, sender, **named):
        if not self.receivers or self.sender_receivers_cache.get(sender) is NO_RECEIVERS:
            return
        sync_receivers, async_receivers = self._live_receivers(sender)
        assert not async_receivers, 'Async receivers not supported'
        for receiver in sync_receivers:
            execute_task_signal_receiver.enqueue(
                receiver_qualname=callable_to_qualname(receiver),
                named=named,
            )
```

### 3. Helper functions to reference receivers by name

```python
def callable_to_qualname(f):
    return f'{f.__module__}::{f.__qualname__}'

def qualname_to_callable(qualname):
    import importlib
    module_name, func_qualname = qualname.split('::', 1)
    module = importlib.import_module(module_name)
    obj = module
    for attr in func_qualname.split('.'):
        obj = getattr(obj, attr)
    return obj
```

### 4. The generic task that executes any receiver

```python
from django_tasks import task

@task()
def execute_task_signal_receiver(*, receiver_qualname, named):
    receiver = qualname_to_callable(receiver_qualname)
    receiver(signal=None, sender=None, **named)
```

### 5. Define your signal and send it inside the transaction

```python
# payment/signals.py
from reliable_signal import Signal
payment_process_completed = Signal()

# payment/models.py
class PaymentProcess(models.Model):
    @classmethod
    def set_status(cls, id, *, succeeded):
        with transaction.atomic():
            payment_process = cls.objects.select_for_update().get(id=id)
            payment_process.status = 'succeeded' if succeeded else 'failed'
            payment_process.save()

            # Inside the transaction — task is committed atomically with the data
            signals.payment_process_completed.send_reliable(
                sender=None,
                payment_process_id=payment_process.id,
            )
        return payment_process
```

### 6. Register receivers as usual

```python
# order/models.py
from django.dispatch import receiver
import payment.signals

class Order(models.Model):
    @staticmethod
    @receiver(payment.signals.payment_process_completed)
    def on_payment_completed(payment_process_id, **kwargs):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                payment_process_id=payment_process_id
            )
            match order.payment_process.status:
                case 'succeeded': order.status = 'completed'
                case 'failed': order.status = 'cancelled'
            order.save()
```

### Testing

Use `ImmediateBackend` so tasks run synchronously in tests:

```python
from django.test import TestCase, override_settings

@override_settings(TASKS={'default': {'BACKEND': 'django_tasks.backends.immediate.ImmediateBackend'}})
class OrderTestCase(TestCase):
    def test_order_completed_on_successful_payment(self):
        order = Order.create(amount=100_00)
        PaymentProcess.set_status(order.payment_process_id, succeeded=True)
        order.refresh_from_db()
        self.assertEqual(order.status, 'completed')
```

## Experiment

This folder is a runnable Django project demonstrating reliable signals via the transactional outbox pattern.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Then open:

- **`/test/`** — interactive test panel with three scenarios: naive signal crash, the gap after commit, and the reliable outbox fix. Each scenario has an explanation, code, and a button to try it
- **`/admin/`** — browse orders, payments, and task results

To use the background worker instead of the test panel's "Process Tasks" button:

```bash
python manage.py db_worker
```

CLI commands:

| Command | What it does |
|---|---|
| `python manage.py seed_data` | Creates sample orders with pending payments |
| `python manage.py complete_payment <id>` | Simulates a payment webhook — triggers the reliable signal |
| `python manage.py complete_payment <id> --fail` | Simulates a failed payment |
| `python manage.py poll_orders` | Polling fallback — finds and syncs stale orders |

Key files:
- `reliable_signal/` — the `ReliableSignal` class and task
- `payment/models.py` — `PaymentProcess` model, sends `send_reliable` inside transaction
- `payment/signals.py` — signal definition using `ReliableSignal`
- `order/models.py` — `Order` model, receiver reacts to payment changes
- `test_views.py` — test panel backend (API endpoints for the interactive demo)

## Key Takeaways

- **Standard Django signals have no delivery guarantees** — if the process crashes between commit and signal send, receivers never fire
- **The fix is the transactional outbox pattern** — enqueue receiver tasks in the same database transaction as the data change
- **Django 6's tasks framework + a database backend** makes this straightforward — no need for Celery or Redis
- **`send_reliable` replaces `send`/`send_robust`** — receivers run in a separate worker process, isolated from the sender
- **Polling is still valuable as a fallback** — a management command that periodically syncs stale records catches anything the signal missed

## Q&A Highlights

- **Do you need Django 6?** The concept works with any database queue. Django 6's tasks framework is convenient but you could use Celery with a database broker or any other task queue
- **What about the outbox pattern?** This is exactly the outbox pattern. The blog post recommends reading about it for the formal definition

## Links

- Blog post with full code: https://hakibenita.com/django-reliable-signals
- Django tasks framework docs: https://docs.djangoproject.com/en/6.0/topics/tasks/
- django-tasks database backend: https://pypi.org/project/django-tasks/

---
*Summarized at DjangoCon Europe 2026*

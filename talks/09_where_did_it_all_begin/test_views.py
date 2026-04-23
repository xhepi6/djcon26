"""
Test panel API for Talk 09: Where Did It All Begin? (django-subatomic).

Endpoints power the interactive /test/ page. Kept outside the banking/ app
so that app stays a clean copy of what the talk describes.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.core.management import call_command
from django.db import connection, reset_queries
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from banking.models import Account, TransferLog
from banking.services import transfer_with_atomic, transfer_with_subatomic


def state_view(request):
    """Everything the /test/ page needs to render in one shot."""
    accounts = [
        {"name": acct.name, "balance": str(acct.balance)}
        for acct in Account.objects.order_by("name")
    ]

    logs = [
        {
            "from": log.from_account.name,
            "to": log.to_account.name,
            "amount": str(log.amount),
            "created_at": log.created_at.isoformat(),
        }
        for log in TransferLog.objects.select_related(
            "from_account", "to_account"
        ).order_by("-created_at")[:20]
    ]

    return JsonResponse({"accounts": accounts, "transfer_log": logs})


@csrf_exempt
@require_POST
def demo_atomic_view(request):
    """Run the atomic() demo transfer and return all SQL queries executed."""
    # Reset balances to known state
    Account.objects.filter(name="Alice").update(balance=Decimal("1000.00"))
    Account.objects.filter(name="Bob").update(balance=Decimal("500.00"))
    TransferLog.objects.all().delete()

    reset_queries()
    connection.force_debug_cursor = True
    error = None
    log = None
    try:
        log = transfer_with_atomic("Alice", "Bob", Decimal("200.00"))
    except Exception as exc:
        error = str(exc)
    finally:
        connection.force_debug_cursor = False

    sql = [q["sql"] for q in connection.queries]

    result = {
        "ok": error is None,
        "description": (
            "Transfer using atomic(). Watch for SAVEPOINT/RELEASE SAVEPOINT "
            "queries from the nested atomic() blocks — even though no partial "
            "rollback is needed."
        ),
        "sql": sql,
        "query_count": len(sql),
        "savepoint_count": sum(
            1 for s in sql if "SAVEPOINT" in s.upper() and "RELEASE" not in s.upper()
        ),
        "release_count": sum(1 for s in sql if "RELEASE SAVEPOINT" in s.upper()),
    }
    if log:
        result["transfer"] = {
            "from": log.from_account.name,
            "to": log.to_account.name,
            "amount": str(log.amount),
        }
    if error:
        result["error"] = error

    # Refresh balances
    result["balances"] = {
        acct.name: str(acct.balance)
        for acct in Account.objects.filter(name__in=["Alice", "Bob"])
    }

    return JsonResponse(result)


@csrf_exempt
@require_POST
def demo_subatomic_view(request):
    """Run the subatomic demo transfer and return all SQL queries executed."""
    # Reset balances to known state
    Account.objects.filter(name="Alice").update(balance=Decimal("1000.00"))
    Account.objects.filter(name="Bob").update(balance=Decimal("500.00"))
    TransferLog.objects.all().delete()

    reset_queries()
    connection.force_debug_cursor = True
    error = None
    log = None
    try:
        log = transfer_with_subatomic("Alice", "Bob", Decimal("200.00"))
    except Exception as exc:
        error = str(exc)
    finally:
        connection.force_debug_cursor = False

    sql = [q["sql"] for q in connection.queries]

    result = {
        "ok": error is None,
        "description": (
            "Transfer using django-subatomic. transaction() at the top, "
            "transaction_required() in helpers. No savepoints — zero extra SQL."
        ),
        "sql": sql,
        "query_count": len(sql),
        "savepoint_count": sum(
            1 for s in sql if "SAVEPOINT" in s.upper() and "RELEASE" not in s.upper()
        ),
        "release_count": sum(1 for s in sql if "RELEASE SAVEPOINT" in s.upper()),
    }
    if log:
        result["transfer"] = {
            "from": log.from_account.name,
            "to": log.to_account.name,
            "amount": str(log.amount),
        }
    if error:
        result["error"] = error

    # Refresh balances
    result["balances"] = {
        acct.name: str(acct.balance)
        for acct in Account.objects.filter(name__in=["Alice", "Bob"])
    }

    return JsonResponse(result)


@csrf_exempt
@require_POST
def seed_view(request):
    """Re-seed the accounts."""
    call_command("seed_data")
    accounts = [
        {"name": acct.name, "balance": str(acct.balance)}
        for acct in Account.objects.order_by("name")
    ]
    return JsonResponse({"ok": True, "accounts": accounts})


@csrf_exempt
@require_POST
def transfer_view(request):
    """
    Perform a transfer between two accounts.

    Expects JSON: {"from": "Alice", "to": "Bob", "amount": "100.00", "mode": "atomic"}
    mode is "atomic" or "subatomic".
    """
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    from_name = payload.get("from")
    to_name = payload.get("to")
    amount_str = payload.get("amount", "100.00")
    mode = payload.get("mode", "atomic")

    if not from_name or not to_name:
        return JsonResponse(
            {"ok": False, "error": "from and to account names required"}, status=400
        )

    try:
        amount = Decimal(str(amount_str))
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "invalid amount"}, status=400)

    if mode not in ("atomic", "subatomic"):
        return JsonResponse(
            {"ok": False, "error": "mode must be 'atomic' or 'subatomic'"}, status=400
        )

    reset_queries()
    connection.force_debug_cursor = True
    error = None
    log = None
    try:
        if mode == "atomic":
            log = transfer_with_atomic(from_name, to_name, amount)
        else:
            log = transfer_with_subatomic(from_name, to_name, amount)
    except Exception as exc:
        error = str(exc)
    finally:
        connection.force_debug_cursor = False

    sql = [q["sql"] for q in connection.queries]

    result = {
        "ok": error is None,
        "mode": mode,
        "sql": sql,
        "query_count": len(sql),
        "savepoint_count": sum(
            1 for s in sql if "SAVEPOINT" in s.upper() and "RELEASE" not in s.upper()
        ),
        "release_count": sum(1 for s in sql if "RELEASE SAVEPOINT" in s.upper()),
    }
    if log:
        result["transfer"] = {
            "from": log.from_account.name,
            "to": log.to_account.name,
            "amount": str(log.amount),
        }
    if error:
        result["error"] = error

    # Refresh all balances
    result["balances"] = {
        acct.name: str(acct.balance) for acct in Account.objects.order_by("name")
    }

    return JsonResponse(result)

"""
Test panel API for Talk 07: Digitising Historical Caving Data.

Provides endpoints for the interactive /test/ page. Separated from app
code so the incidents module stays clean.
"""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from incidents.fields import FuzzyDate
from incidents.models import (
    Incident,
    IncidentSeverity,
    Location,
    OperationRun,
    OperationStatus,
)
from incidents.operations import get_registry


def state_view(request):
    """Return all incidents, operations, and location tree data."""
    registry = get_registry()
    op_names = [o.name() for o in registry]

    # Build status map
    runs = OperationRun.objects.all()
    status_map: dict[tuple[int, str], dict] = {}
    for r in runs:
        status_map[(r.incident_id, r.operation_name)] = {
            "status": r.status,
            "error": r.error_message,
        }

    incidents = []
    for inc in Incident.objects.select_related("location").order_by("id"):
        ops = {}
        for name in op_names:
            info = status_map.get((inc.id, name))
            ops[name] = {
                "status": info["status"] if info else "pending",
                "error": info["error"] if info else "",
            }
        incidents.append({
            "id": inc.id,
            "raw_text": inc.raw_text,
            "raw_date_text": inc.raw_date_text,
            "raw_location_text": inc.raw_location_text,
            "cleaned_text": inc.cleaned_text,
            "occurred_at": str(inc.occurred_at) if inc.occurred_at else None,
            "occurred_at_storage": inc.occurred_at.to_storage() if inc.occurred_at else None,
            "location": str(inc.location) if inc.location else None,
            "severity": inc.severity,
            "operations": ops,
        })

    # Build location tree
    tree = []
    for root in Location.get_root_nodes():
        tree.append(_tree_node(root))

    return JsonResponse({
        "incidents": incidents,
        "op_names": op_names,
        "tree": tree,
        "summary": {
            "total": len(incidents),
            "success": OperationRun.objects.filter(status=OperationStatus.SUCCESS).count(),
            "failed": OperationRun.objects.filter(status=OperationStatus.FAILED).count(),
        },
    })


def _tree_node(node: Location) -> dict:
    """Recursively build a tree node dict."""
    children = []
    for child in node.get_children():
        children.append(_tree_node(child))
    incident_count = node.incidents.count()
    return {
        "name": node.name,
        "level": node.level,
        "incident_count": incident_count,
        "children": children,
    }


def fuzzy_date_demo_view(request):
    """Show all FuzzyDate precision levels and their storage format."""
    import datetime as dt

    samples = [
        ("Year only", FuzzyDate.from_year(1971)),
        ("Season", FuzzyDate.from_season(1996, "autumn")),
        ("Month", FuzzyDate.from_month(1985, 8)),
        ("Day", FuzzyDate.from_date(dt.date(2024, 3, 15))),
    ]

    results = []
    for label, fd in samples:
        results.append({
            "label": label,
            "input": label,
            "display": str(fd),
            "storage": fd.to_storage(),
            "precision": str(fd.precision),
        })

    return JsonResponse({"dates": results})


@csrf_exempt
@require_POST
def reset_and_seed_view(request):
    """Wipe all data, re-seed, and run the pipeline."""
    from django.core.management import call_command

    call_command("seed_raw", "--reset")
    call_command("process")

    return JsonResponse({"ok": True, "message": "Reset, seeded, and processed."})


@csrf_exempt
@require_POST
def run_pipeline_view(request):
    """Run the pipeline on all incidents."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command("process", stdout=out)

    return JsonResponse({"ok": True, "output": out.getvalue()})


@csrf_exempt
@require_POST
def rerun_pipeline_view(request):
    """Re-run the entire pipeline from scratch."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    call_command("process", "--rerun", stdout=out)

    return JsonResponse({"ok": True, "output": out.getvalue()})


def tree_query_view(request):
    """Demonstrate a tree descendant query: count incidents under a node."""
    node_name = request.GET.get("node", "USA")
    node = Location.objects.filter(name=node_name).first()
    if not node:
        return JsonResponse({"ok": False, "error": f"No location named '{node_name}'"})

    descendants = node.get_descendants()
    descendant_ids = list(descendants.values_list("id", flat=True))
    count = Incident.objects.filter(
        location_id__in=[node.id, *descendant_ids]
    ).count()

    breadcrumb = " > ".join(
        a.name for a in list(node.get_ancestors()) + [node]
    )

    return JsonResponse({
        "ok": True,
        "node": node.name,
        "level": node.level,
        "breadcrumb": breadcrumb,
        "descendant_locations": descendants.count(),
        "incident_count": count,
    })

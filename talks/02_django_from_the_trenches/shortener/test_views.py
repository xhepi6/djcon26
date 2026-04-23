"""
Views for the /test/ page — runs EXPLAIN ANALYZE for each index type.
Separated from the app views so the test infrastructure doesn't mix
with the actual URL shortener endpoints.
"""

import re
from datetime import timedelta

from django.db import connection
from django.db.models import F, Func
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import ShortUrl
from .queries import explain, find_by_date_range, find_by_domain, find_by_url, find_unused


def _parse_plan(plan_text):
    """Extract scan type, index name, and execution time from EXPLAIN ANALYZE output."""
    scan_type = "Unknown"
    index_name = ""
    exec_time = ""

    if "Index Only Scan" in plan_text:
        scan_type = "Index Only Scan"
    elif "Bitmap Index Scan" in plan_text:
        scan_type = "Bitmap Index Scan"
    elif "Index Scan" in plan_text:
        scan_type = "Index Scan"
    elif "Seq Scan" in plan_text:
        scan_type = "Seq Scan"

    m = re.search(r"(?:Index Only Scan|Bitmap Index Scan|Index Scan) (?:using|on) (\S+)", plan_text)
    if m:
        index_name = m.group(1)

    m = re.search(r"Execution Time: ([\d.]+) ms", plan_text)
    if m:
        exec_time = m.group(1) + " ms"

    heap_fetches = ""
    m = re.search(r"Heap Fetches: (\d+)", plan_text)
    if m:
        heap_fetches = m.group(1)

    return {
        "scan_type": scan_type,
        "index_name": index_name,
        "exec_time": exec_time,
        "heap_fetches": heap_fetches,
        "raw": plan_text,
    }


def _format_sql(sql):
    """Minimal SQL formatting — uppercase keywords, newlines before clauses."""
    keywords = ["SELECT", "FROM", "WHERE", "AND", "OR", "ORDER BY",
                "GROUP BY", "INNER JOIN", "LEFT JOIN", "LIMIT"]
    result = str(sql)
    for kw in keywords:
        result = re.sub(rf'\b{kw}\b', f'\n{kw}', result, flags=re.IGNORECASE)
    return result.strip()


@require_GET
def explain_view(request):
    """Run EXPLAIN ANALYZE for each index type. Returns parsed JSON for the /test/ page."""
    results = {}

    # Index sizes
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass))
            FROM pg_indexes
            WHERE tablename = 'shortener_shorturl'
            ORDER BY pg_relation_size(indexname::regclass) DESC;
        """)
        results["index_sizes"] = [
            {"name": name, "size": size} for name, size in cursor.fetchall()
        ]

    # 1. Covering index
    sample_key = ShortUrl.objects.order_by("id").values_list("key", flat=True).first() or "abc"
    qs = ShortUrl.objects.filter(key=sample_key).values_list("url", flat=True)
    results["covering"] = {
        "sql": _format_sql(qs.query),
        **_parse_plan(qs.explain(analyze=True)),
    }

    # 2. Function-based index (domain search)
    qs = find_by_domain("example.com")
    results["fbi"] = {
        "sql": _format_sql(qs.query),
        **_parse_plan(explain(qs)),
    }

    # 3. Partial index (unused)
    qs = find_unused()
    results["partial"] = {
        "sql": _format_sql(qs.query),
        **_parse_plan(explain(qs)),
    }

    # 4. Hash index (reverse lookup)
    sample_url = ShortUrl.objects.order_by("id").values_list("url", flat=True).first() or ""
    qs = find_by_url(sample_url)
    results["hash"] = {
        "sql": _format_sql(qs.query),
        **_parse_plan(explain(qs)),
    }

    # 5. BRIN index (date range)
    end = timezone.now()
    start = end - timedelta(days=30)
    qs = find_by_date_range(start, end)
    results["brin"] = {
        "sql": _format_sql(qs.query),
        **_parse_plan(explain(qs)),
    }

    # 6. alias() vs annotate()
    expr = Func(F("url"), function="SUBSTRING",
                template="%(function)s(%(expressions)s from '.*://([^/]*)')")
    qs_annotate = ShortUrl.objects.annotate(domain=expr).filter(domain="example.com")
    qs_alias = ShortUrl.objects.alias(domain=expr).filter(domain="example.com")
    results["alias_vs_annotate"] = {
        "annotate_sql": _format_sql(qs_annotate.query),
        "alias_sql": _format_sql(qs_alias.query),
    }

    return JsonResponse(results)

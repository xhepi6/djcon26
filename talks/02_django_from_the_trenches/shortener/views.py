from datetime import timedelta

from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from .queries import find_by_date_range, find_by_domain, find_by_url, find_unused, resolve


def resolve_url(request, key):
    """Redirect from short key to full URL (covering index)."""
    url = resolve(key)
    if url is None:
        raise Http404
    return redirect(url)


def find_by_domain_view(request, domain):
    """List short URLs for a domain (function-based index)."""
    qs = find_by_domain(domain).values("key", "url", "hits")[:50]
    return JsonResponse(list(qs), safe=False)


def find_unused_view(request):
    """List unused short URLs (partial index)."""
    qs = find_unused().values("key", "url")[:50]
    return JsonResponse(list(qs), safe=False)


def find_by_url_view(request):
    """Reverse lookup by exact URL (hash index)."""
    url = request.GET.get("url", "")
    if not url:
        return JsonResponse({"error": "?url= parameter required"}, status=400)
    qs = find_by_url(url).values("key", "url", "hits")[:50]
    return JsonResponse(list(qs), safe=False)


def find_by_date_range_view(request):
    """Find short URLs by date range (BRIN index)."""
    days = int(request.GET.get("days", 30))
    end = timezone.now()
    start = end - timedelta(days=days)
    qs = find_by_date_range(start, end).values("key", "url", "created_at")[:50]
    data = list(qs)
    for row in data:
        row["created_at"] = row["created_at"].isoformat()
    return JsonResponse(data, safe=False)

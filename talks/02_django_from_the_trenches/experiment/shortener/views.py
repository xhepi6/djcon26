from django.http import Http404, JsonResponse
from django.shortcuts import redirect

from .queries import find_by_domain, find_unused, resolve


def resolve_url(request, key):
    """Redirect from short key to full URL."""
    url = resolve(key)
    if url is None:
        raise Http404
    return redirect(url)


def find_by_domain_view(request, domain):
    """List short URLs for a domain."""
    qs = find_by_domain(domain).values("key", "url", "hits")[:50]
    return JsonResponse(list(qs), safe=False)


def find_unused_view(request):
    """List unused short URLs."""
    qs = find_unused().values("key", "url")[:50]
    return JsonResponse(list(qs), safe=False)

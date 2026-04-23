"""
Test panel API for Talk 10: What's in Your Dependencies?

Endpoints power the interactive /test/ page. Kept out of the deps/ app
so that app stays a clean copy of what the talk describes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

BASE_DIR = Path(__file__).resolve().parent


def state_view(request):
    """Return installed packages, requirements.txt, and requirements-hashed.txt."""
    # Get installed packages via pip list
    packages = []
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
    except Exception as exc:
        packages = [{"error": str(exc)}]

    # Read requirements files
    req_content = ""
    req_path = BASE_DIR / "requirements.txt"
    if req_path.exists():
        req_content = req_path.read_text()

    hashed_content = ""
    hashed_path = BASE_DIR / "requirements-hashed.txt"
    if hashed_path.exists():
        hashed_content = hashed_path.read_text()

    return JsonResponse({
        "packages": packages,
        "requirements": req_content,
        "requirements_hashed": hashed_content,
        "package_count": len(packages),
    })


@csrf_exempt
@require_POST
def audit_view(request):
    """Run pip-audit on the current environment and return results as JSON."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "-f", "json"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        raw_output = result.stdout or result.stderr

        # pip-audit outputs JSON on stdout when -f json is used
        if result.stdout.strip():
            try:
                audit_data = json.loads(result.stdout)
                vulnerabilities = audit_data.get("vulnerabilities", [])
                return JsonResponse({
                    "ok": True,
                    "vulnerabilities": vulnerabilities,
                    "vuln_count": len(vulnerabilities),
                    "clean": len(vulnerabilities) == 0,
                    "raw": result.stdout[:2000],
                })
            except json.JSONDecodeError:
                pass

        # pip-audit not installed or failed — simulate with a note
        if result.returncode == 127 or "No module named pip_audit" in (result.stderr or ""):
            return JsonResponse({
                "ok": False,
                "error": "pip-audit not installed. Run: pip install pip-audit",
                "install_hint": "pip install pip-audit",
                "vulnerabilities": [],
                "simulated": True,
            })

        # Ran but found no vulnerabilities (exit 0) or found some (exit 1)
        return JsonResponse({
            "ok": True,
            "vulnerabilities": [],
            "vuln_count": 0,
            "clean": result.returncode == 0,
            "raw": raw_output[:2000],
            "return_code": result.returncode,
        })

    except FileNotFoundError:
        return JsonResponse({
            "ok": False,
            "error": "pip-audit not found. Run: pip install pip-audit",
            "vulnerabilities": [],
            "simulated": True,
        })
    except subprocess.TimeoutExpired:
        return JsonResponse({
            "ok": False,
            "error": "pip-audit timed out after 60 seconds.",
            "vulnerabilities": [],
        })
    except Exception as exc:
        return JsonResponse({
            "ok": False,
            "error": str(exc),
            "vulnerabilities": [],
        })


@csrf_exempt
@require_POST
def check_view(request):
    """Query PyPI JSON API for package health info."""
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    package = payload.get("package", "").strip()
    if not package:
        return JsonResponse({"ok": False, "error": "package name required"}, status=400)

    url = f"https://pypi.org/pypi/{package}/json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return JsonResponse({
                "ok": False,
                "error": f"Package '{package}' not found on PyPI.",
                "hint": "Check the spelling — typosquatting attacks rely on small misspellings.",
            }, status=404)
        return JsonResponse({"ok": False, "error": f"HTTP {exc.code} from PyPI"}, status=502)
    except urllib.error.URLError as exc:
        return JsonResponse({"ok": False, "error": f"Network error: {exc.reason}"}, status=502)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)

    info = data["info"]
    releases = data.get("releases", {})

    # Find the latest release date across all versions
    latest_date = None
    for version_files in releases.values():
        for file_info in version_files:
            upload_time = file_info.get("upload_time_iso_8601")
            if upload_time:
                dt = datetime.fromisoformat(upload_time)
                if latest_date is None or dt > latest_date:
                    latest_date = dt

    days_since_release = None
    if latest_date:
        days_since_release = (datetime.now(timezone.utc) - latest_date).days

    version_count = len(releases)
    project_urls = info.get("project_urls") or {}

    has_repo = any(
        "github.com" in url or "gitlab.com" in url or "codeberg.org" in url
        for url in project_urls.values()
    )

    # Health score: 0-100 based on signals
    score = 50
    signals = []

    if days_since_release is not None:
        if days_since_release <= 90:
            score += 15
            signals.append({"label": "Active", "detail": f"Released {days_since_release} days ago", "status": "good"})
        elif days_since_release <= 365:
            score += 5
            signals.append({"label": "Mostly active", "detail": f"Released {days_since_release} days ago", "status": "warn"})
        else:
            score -= 20
            signals.append({"label": "Potentially abandoned", "detail": f"Last release {days_since_release} days ago", "status": "bad"})

    if version_count > 10:
        score += 15
        signals.append({"label": "Established", "detail": f"{version_count} versions on PyPI", "status": "good"})
    elif version_count > 3:
        score += 5
        signals.append({"label": "Some history", "detail": f"{version_count} versions on PyPI", "status": "warn"})
    else:
        score -= 15
        signals.append({"label": "Very new", "detail": f"Only {version_count} version(s) — higher risk", "status": "bad"})

    if has_repo:
        score += 10
        signals.append({"label": "Source repo linked", "detail": "GitHub/GitLab/Codeberg found in project URLs", "status": "good"})
    else:
        score -= 5
        signals.append({"label": "No source repo", "detail": "No public repository in project URLs", "status": "warn"})

    license_val = info.get("license") or ""
    if license_val:
        score += 10
        signals.append({"label": "License declared", "detail": license_val, "status": "good"})
    else:
        signals.append({"label": "No license", "detail": "License not declared on PyPI", "status": "warn"})

    score = max(0, min(100, score))

    return JsonResponse({
        "ok": True,
        "name": info["name"],
        "version": info["version"],
        "summary": info.get("summary", ""),
        "license": license_val or "Not specified",
        "requires_python": info.get("requires_python") or "Any",
        "author": info.get("author") or info.get("maintainer") or "Unknown",
        "author_email": info.get("author_email") or info.get("maintainer_email") or "",
        "home_page": info.get("home_page") or info.get("project_url") or "",
        "project_urls": project_urls,
        "version_count": version_count,
        "last_release": latest_date.strftime("%Y-%m-%d") if latest_date else None,
        "days_since_release": days_since_release,
        "has_repo": has_repo,
        "health_score": score,
        "signals": signals,
        "pypi_url": f"https://pypi.org/project/{package}/",
        "deps_dev_url": f"https://deps.dev/pypi/{package}",
        "socket_dev_url": f"https://socket.dev/pypi/package/{package}",
    })


@csrf_exempt
@require_POST
def hashes_view(request):
    """Show what hash-pinned requirements look like for the current requirements.txt."""
    req_path = BASE_DIR / "requirements.txt"
    if not req_path.exists():
        return JsonResponse({"ok": False, "error": "requirements.txt not found"}, status=404)

    plain_content = req_path.read_text()

    # Read the example hashed file
    hashed_path = BASE_DIR / "requirements-hashed.txt"
    hashed_example = hashed_path.read_text() if hashed_path.exists() else ""

    # Explain the difference
    explanation = {
        "plain": {
            "title": "Plain version pin",
            "example": "django>=5.1",
            "what_it_does": "Tells pip WHICH version range to install.",
            "risk": "If the file on PyPI is replaced (even at the same version), pip installs the tampered file.",
        },
        "hashed": {
            "title": "Hash-pinned requirement",
            "example": "django==5.2 \\\n    --hash=sha256:abc123...",
            "what_it_does": "Tells pip WHICH EXACT FILE to accept. If the hash doesn't match, installation fails.",
            "protects_against": [
                "Compromised maintainer accounts publishing tampered files",
                "Man-in-the-middle attacks on package downloads",
                "PyPI mirror tampering",
            ],
        },
        "how_to_generate": [
            {
                "tool": "uv (recommended)",
                "command": "uv pip compile requirements.in --generate-hashes -o requirements.txt",
            },
            {
                "tool": "pip-tools",
                "command": "pip-compile --generate-hashes requirements.in",
            },
            {
                "tool": "pip hash (manual)",
                "command": "pip download django==5.2 --no-deps -d /tmp/wheels && pip hash /tmp/wheels/django-5.2-py3-none-any.whl",
            },
        ],
        "install_with_hashes": "pip install --require-hashes -r requirements.txt",
    }

    return JsonResponse({
        "ok": True,
        "plain_requirements": plain_content,
        "hashed_example": hashed_example,
        "explanation": explanation,
    })

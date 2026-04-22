"""
Evaluate a PyPI package before installing it.

Queries the PyPI JSON API for basic health signals:
- Last release date, total versions, release history
- Project links, license, Python version requirements
- Whether a source repository is linked

This is the "look before you install" step from the talk.
"""

import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from django.core.management.base import BaseCommand


PYPI_API = "https://pypi.org/pypi/{}/json"


class Command(BaseCommand):
    help = "Evaluate a PyPI package's health before installing it"

    def add_arguments(self, parser):
        parser.add_argument("package", type=str, help="Package name to check")

    def handle(self, *args, **options):
        package = options["package"]
        self.stdout.write(self.style.WARNING(f"\nChecking: {package}\n"))

        try:
            data = self._fetch_pypi(package)
        except HTTPError as e:
            if e.code == 404:
                self.stdout.write(self.style.ERROR(f"Package '{package}' not found on PyPI."))
                self.stdout.write(
                    "Double-check the name. Typosquatting attacks rely on "
                    "small misspellings."
                )
                return
            raise

        info = data["info"]
        releases = data["releases"]

        # Basic info
        self.stdout.write(f"  Name:        {info['name']}")
        self.stdout.write(f"  Version:     {info['version']}")
        self.stdout.write(f"  Summary:     {info.get('summary', 'N/A')}")
        self.stdout.write(f"  License:     {info.get('license') or 'Not specified'}")
        self.stdout.write(f"  Python:      {info.get('requires_python') or 'Any'}")
        self.stdout.write(f"  Homepage:    {info.get('home_page') or info.get('project_url') or 'N/A'}")

        # Maintainer info
        author = info.get("author") or info.get("maintainer") or "Unknown"
        author_email = info.get("author_email") or info.get("maintainer_email") or ""
        self.stdout.write(f"  Author:      {author} {author_email}")

        # Release history
        version_count = len(releases)
        self.stdout.write(f"  Versions:    {version_count} total")

        # Find the latest release date
        latest_release_date = self._latest_release_date(releases)
        if latest_release_date:
            age = datetime.now(timezone.utc) - latest_release_date
            self.stdout.write(
                f"  Last release: {latest_release_date.strftime('%Y-%m-%d')} "
                f"({age.days} days ago)"
            )

        # Project URLs
        project_urls = info.get("project_urls") or {}
        if project_urls:
            self.stdout.write("  Links:")
            for label, url in project_urls.items():
                self.stdout.write(f"    {label}: {url}")

        # Health signals
        self.stdout.write(self.style.WARNING("\n  Health signals:"))

        # Check age
        if latest_release_date:
            days_since = (datetime.now(timezone.utc) - latest_release_date).days
            if days_since > 365:
                self.stdout.write(
                    self.style.ERROR(f"    [!] Last release was {days_since} days ago — may be abandoned")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"    [ok] Active — released {days_since} days ago")
                )

        # Check version count (very new packages are riskier)
        if version_count <= 2:
            self.stdout.write(
                self.style.ERROR(f"    [!] Only {version_count} version(s) — very new package")
            )
        elif version_count <= 5:
            self.stdout.write(
                self.style.WARNING(f"    [~] {version_count} versions — relatively new")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"    [ok] {version_count} versions — established history")
            )

        # Check for source repo
        has_repo = any(
            "github.com" in url or "gitlab.com" in url or "codeberg.org" in url
            for url in project_urls.values()
        )
        if has_repo:
            self.stdout.write(self.style.SUCCESS("    [ok] Source repository linked"))
        else:
            self.stdout.write(self.style.WARNING("    [~] No source repository found in project URLs"))

        # Suggest further checks
        self.stdout.write(self.style.WARNING("\n  Next steps:"))
        self.stdout.write(f"    - Check deps.dev:   https://deps.dev/pypi/{package}")
        self.stdout.write(f"    - Check Socket.dev: https://socket.dev/pypi/package/{package}")
        self.stdout.write(f"    - Check Scorecard:  https://scorecard.dev/ (search the repo URL)")
        self.stdout.write(f"    - Check PyPI page:  https://pypi.org/project/{package}/")
        self.stdout.write("")

    def _fetch_pypi(self, package):
        url = PYPI_API.format(package)
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def _latest_release_date(self, releases):
        """Find the upload date of the most recent release."""
        latest = None
        for version_files in releases.values():
            for file_info in version_files:
                upload_time = file_info.get("upload_time_iso_8601")
                if upload_time:
                    dt = datetime.fromisoformat(upload_time)
                    if latest is None or dt > latest:
                        latest = dt
        return latest

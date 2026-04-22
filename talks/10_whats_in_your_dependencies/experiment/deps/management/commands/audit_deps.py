"""
Wraps pip-audit to scan the current environment for known vulnerabilities.

pip-audit checks installed packages against the OSV database (osv.dev).
This command makes it easy to run from Django's manage.py.
"""

import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scan installed packages for known vulnerabilities using pip-audit"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Attempt to auto-update vulnerable packages",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Output results as JSON",
        )
        parser.add_argument(
            "-r",
            "--requirement",
            type=str,
            help="Scan a requirements file instead of the environment",
        )

    def handle(self, *args, **options):
        cmd = [sys.executable, "-m", "pip_audit"]

        if options["fix"]:
            cmd.append("--fix")
        if options["json_output"]:
            cmd.extend(["-f", "json"])
        if options["requirement"]:
            cmd.extend(["-r", options["requirement"]])

        self.stdout.write(self.style.WARNING("Running pip-audit...\n"))
        self.stdout.write(f"  Command: {' '.join(cmd)}\n")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            self.stdout.write(result.stdout)
        if result.stderr:
            self.stderr.write(result.stderr)

        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS("\nNo vulnerabilities found."))
        else:
            self.stdout.write(
                self.style.ERROR(
                    "\nVulnerabilities found! Review the output above."
                )
            )
            self.stdout.write(
                "Run with --fix to attempt automatic updates, or update "
                "packages manually."
            )

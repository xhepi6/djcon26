"""
Demonstrates hash-pinned requirements.

Shows the difference between a plain pin (django==5.2) and a hash pin.
Hash pins protect against tampered files on PyPI — if the file changes,
pip refuses to install it.
"""

import subprocess
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show how hash-pinned requirements work"

    def add_arguments(self, parser):
        parser.add_argument(
            "package",
            nargs="?",
            default="django",
            help="Package to generate hashes for (default: django)",
        )

    def handle(self, *args, **options):
        package = options["package"]

        self.stdout.write(self.style.WARNING("=== Hash-Pinned Requirements ===\n"))

        self.stdout.write("A version pin tells pip WHICH version to install:")
        self.stdout.write(self.style.HTTP_INFO(f"  {package}==5.2\n"))

        self.stdout.write("A hash pin tells pip WHICH EXACT FILE to accept:")
        self.stdout.write(self.style.HTTP_INFO(
            f"  {package}==5.2 \\\n"
            f"      --hash=sha256:abc123...\n"
        ))

        self.stdout.write("If the file on PyPI changes (even for the same version),")
        self.stdout.write("pip refuses to install it. This protects against:")
        self.stdout.write("  - Compromised maintainer accounts")
        self.stdout.write("  - Man-in-the-middle attacks")
        self.stdout.write("  - PyPI mirror tampering\n")

        # Generate real hashes for an installed package
        self.stdout.write(self.style.WARNING("=== Generating hashes ===\n"))
        self.stdout.write(f"Finding cached wheel for '{package}'...\n")

        # Use pip cache to find the wheel, then hash it
        result = subprocess.run(
            [sys.executable, "-m", "pip", "cache", "list", package],
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            self.stdout.write("Cached files:")
            self.stdout.write(result.stdout)
        else:
            self.stdout.write("No cached wheels found.\n")

        # Show how to generate hashes with pip compile
        self.stdout.write(self.style.WARNING("\n=== How to generate a hashed lockfile ===\n"))
        self.stdout.write("Option 1 — uv (fastest):")
        self.stdout.write(self.style.HTTP_INFO(
            "  uv pip compile requirements.in --generate-hashes -o requirements.txt"
        ))
        self.stdout.write("\nOption 2 — pip-tools:")
        self.stdout.write(self.style.HTTP_INFO(
            "  pip-compile --generate-hashes requirements.in"
        ))
        self.stdout.write("\nOption 3 — pip hash (manual, one file at a time):")
        self.stdout.write(self.style.HTTP_INFO(
            "  pip download django==5.2 --no-deps -d /tmp/wheels\n"
            "  pip hash /tmp/wheels/django-5.2-py3-none-any.whl"
        ))
        self.stdout.write("\nInstall with hash verification:")
        self.stdout.write(self.style.HTTP_INFO(
            "  pip install --require-hashes -r requirements.txt"
        ))
        self.stdout.write(self.style.HTTP_INFO(
            "  uv pip install --require-hashes -r requirements.txt"
        ))

        # Reference the example file
        self.stdout.write(self.style.WARNING(
            "\nSee requirements-hashed.txt for an example of the format."
        ))

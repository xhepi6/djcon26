"""Demonstrate just-in-time access by watching one UserRole expire.

Sets carol's librarian assignment to expire in --seconds N and polls
has_perm() every second until it flips from True to False.
"""

import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from rbac.models import UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Make carol's librarian role expire in N seconds; poll has_perm every second."

    def add_arguments(self, parser):
        parser.add_argument("--seconds", type=int, default=3)

    def handle(self, *args, seconds, **options):
        carol = User.objects.get(username="carol")
        assignment = UserRole.objects.filter(user=carol, role__name="librarian").first()
        if assignment is None:
            self.stdout.write(self.style.ERROR(
                "No librarian assignment for carol. Run `seed_data` first."
            ))
            return

        expires_at = timezone.now() + timezone.timedelta(seconds=seconds)
        assignment.expires_at = expires_at
        assignment.save()

        self.stdout.write(
            f"carol's librarian assignment now expires at "
            f"{expires_at.isoformat(timespec='seconds')} (in {seconds}s).\n"
            f"Polling has_perm('library.add_book') every second:\n"
        )

        for i in range(seconds + 3):
            result = carol.has_perm("library.add_book")
            tag = self.style.SUCCESS("True ") if result else self.style.WARNING("False")
            self.stdout.write(f"  t+{i:>2}s  has_perm = {tag}")
            if not result and i > seconds:
                break
            time.sleep(1)

"""
Showcase the FuzzyDate field in isolation: every precision level, how
each one stores on disk, how it renders back out, and how lexicographic
ordering on the stored value gives you sensible chronological sort.
"""

from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand

from incidents.fields import FuzzyDate


class Command(BaseCommand):
    help = "Demonstrate the FuzzyDate custom model field."

    def handle(self, *args, **options):
        samples = [
            FuzzyDate.from_year(1971),
            FuzzyDate.from_season(1996, "autumn"),
            FuzzyDate.from_month(1985, 8),
            FuzzyDate.from_date(dt.date(2024, 3, 15)),
            FuzzyDate.from_date(dt.date(2024, 3, 16)),
            FuzzyDate.from_season(2008, "spring"),
        ]

        self.stdout.write(f"{'human':<20}  {'precision':<8}  on-disk (lex-sortable)")
        self.stdout.write("-" * 70)
        for fd in samples:
            self.stdout.write(
                f"{str(fd):<20}  {str(fd.precision):<8}  {fd.to_storage()}"
            )

        self.stdout.write("\nChronological order (from lexicographic sort on storage):")
        for fd in sorted(samples, key=lambda x: x.to_storage()):
            self.stdout.write(f"  {fd.to_storage():<28}  {fd}")

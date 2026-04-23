"""
Seed a small set of fake caving-incident records that exercise every
operation in the pipeline: every date format, the location tree at every
depth, and deliberately-noisy OCR text for the LLM stubs to rewrite.

One record (#8) has text that the critic will reject even after the
rewrite — that's the intended FAILED outcome.
"""

from django.core.management.base import BaseCommand

from incidents.models import Incident, Location, OperationRun


RAW = [
    # (raw_text, raw_date_text, raw_location_text)
    (
        "Caver slipped during rap-  pel and suffered a broken ankle .",
        "15 March 2024",
        "Carlsbad Caverns, New Mexico, USA",
    ),
    (
        "Small party became lost; self-rescued after 8 hours.",
        "August 1985",
        "Mammoth Cave, Kentucky, USA",
    ),
    (
        "Diver encountered  strong current and was rescued by team.",
        "Autumn 1996",
        "Ginnie Springs, Florida, USA",
    ),
    (
        "Minor scrape, no medical attention required.",
        "1971",
        "Arizona, USA",
    ),
    (
        "Rope abrasion caused   fatal fall from 40 m pitch.",
        "October 4, 1982",
        "Ellison's Cave, Georgia, USA",
    ),
    (
        "Lost light; party exited safely.",
        "Winter 2010",
        "Jewel Cave, South Dakota, USA",
    ),
    (
        "Rock fall resulted in  injury to the lead caver.",
        "6 June 2019",
        "Sistema Huautla, Oaxaca, Mexico",
    ),
    # This one's cleaned_text will still contain the ??? placeholder that
    # the rewrite can't resolve. The critic should flag it as FAILED —
    # exactly the self-check pattern the talk describes.
    (
        "Party of three descended ??? pitch; ??? injury sustained.",
        "Spring 2008",
        "Unknown, USA",
    ),
]


class Command(BaseCommand):
    help = "Populate a small set of fake incidents that exercise every step."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="wipe incidents, locations and operation runs first",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            # Order matters — OperationRun FK'd to Incident, Incident FK'd
            # to Location.
            OperationRun.objects.all().delete()
            Incident.objects.all().delete()
            Location.objects.all().delete()
            self.stdout.write("wiped existing data.")

        for text, date_text, location_text in RAW:
            Incident.objects.create(
                raw_text=text,
                raw_date_text=date_text,
                raw_location_text=location_text,
            )

        self.stdout.write(self.style.SUCCESS(
            f"inserted {len(RAW)} raw incidents. "
            "Run `python manage.py process` next."
        ))

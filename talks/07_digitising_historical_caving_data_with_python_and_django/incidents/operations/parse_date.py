"""
ParseDate — turn ``raw_date_text`` into a ``FuzzyDate`` on ``occurred_at``.

Demonstrates a step that reads raw text and writes a structured field.
Recognises:

    "1971"            → year precision
    "August 1985"     → month precision
    "Autumn 1996"     → season precision
    "15 March 2024"   → day precision
"""

from __future__ import annotations

import datetime as dt
import re

from incidents.fields import FuzzyDate, SEASON_MONTHS
from incidents.models import Incident
from incidents.operations.base import Operation, register


MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"],
        start=1,
    )
}
MONTH_RE = "|".join(MONTHS)
SEASON_RE = "|".join(SEASON_MONTHS)

PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(rf"^(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_RE})\s+(?P<year>\d{{4}})$", re.I), "day"),
    (re.compile(rf"^(?P<month>{MONTH_RE})\s+(?P<day>\d{{1,2}}),?\s+(?P<year>\d{{4}})$", re.I), "day"),
    (re.compile(rf"^(?P<month>{MONTH_RE})\s+(?P<year>\d{{4}})$", re.I), "month"),
    (re.compile(rf"^(?P<season>{SEASON_RE})\s+(?P<year>\d{{4}})$", re.I), "season"),
    (re.compile(r"^(?P<year>\d{4})$"), "year"),
]


@register
class ParseDate(Operation):
    label = "parse date"

    def should_run(self, incident: Incident) -> bool:
        # Skip if already parsed or no raw text to parse.
        return bool(incident.raw_date_text) and incident.occurred_at is None

    def run(self, incident: Incident) -> None:
        text = incident.raw_date_text.strip()
        for pattern, precision in PATTERNS:
            m = pattern.match(text)
            if not m:
                continue
            g = m.groupdict()
            year = int(g["year"])
            if precision == "year":
                incident.occurred_at = FuzzyDate.from_year(year)
            elif precision == "season":
                incident.occurred_at = FuzzyDate.from_season(year, g["season"])
            elif precision == "month":
                incident.occurred_at = FuzzyDate.from_month(year, MONTHS[g["month"].lower()])
            elif precision == "day":
                incident.occurred_at = FuzzyDate.from_date(
                    dt.date(year, MONTHS[g["month"].lower()], int(g["day"]))
                )
            incident.save(update_fields=["occurred_at"])
            return

        raise ValueError(f"unrecognised date format: {text!r}")

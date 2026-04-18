"""
A custom model field for storing fuzzy historical dates.

The caving-incident reports use every date format you can imagine:

    "15 March 2024"          → day precision
    "August 1985"            → month precision
    "Autumn 1996"            → season precision
    "1971"                   → year precision

A plain ``DateField`` loses information: if you store ``1996-09-01`` for
"Autumn 1996", the system thinks you know it happened on 1 September. Round-
tripping to the UI would render a false specificity.

So we keep **precision** alongside the date. The field value is a
``FuzzyDate`` dataclass; Django (de)serialises it to/from a short string
via ``to_python`` / ``get_prep_value`` / ``from_db_value``.

Storage format (single TEXT column, lexicographically sortable by day):

    "1996-01-01:year"
    "1996-09-01:season:autumn"
    "1985-08-01:month"
    "2024-03-15:day"
"""

from __future__ import annotations

import datetime as dt
import enum
from dataclasses import dataclass
from typing import Any

from django.core import exceptions
from django.db import models


class Precision(enum.StrEnum):
    YEAR = "year"
    SEASON = "season"
    MONTH = "month"
    DAY = "day"


# Seasons → a representative month so we still have a real Date for ordering.
# Northern-hemisphere bias matches the caving reports (all US incidents).
SEASON_MONTHS = {
    "spring": 3,
    "summer": 6,
    "autumn": 9,
    "winter": 12,
}
SEASON_LABELS = {v: k for k, v in SEASON_MONTHS.items()}


@dataclass(frozen=True)
class FuzzyDate:
    """A historical date with a declared precision."""

    year: int
    precision: Precision
    month: int | None = None    # set for MONTH / DAY / SEASON
    day: int | None = None      # set for DAY
    season: str | None = None   # set for SEASON

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_year(cls, year: int) -> FuzzyDate:
        return cls(year=year, precision=Precision.YEAR)

    @classmethod
    def from_season(cls, year: int, season: str) -> FuzzyDate:
        season = season.lower()
        if season not in SEASON_MONTHS:
            raise ValueError(f"unknown season: {season!r}")
        return cls(
            year=year,
            precision=Precision.SEASON,
            month=SEASON_MONTHS[season],
            season=season,
        )

    @classmethod
    def from_month(cls, year: int, month: int) -> FuzzyDate:
        return cls(year=year, precision=Precision.MONTH, month=month)

    @classmethod
    def from_date(cls, d: dt.date) -> FuzzyDate:
        return cls(
            year=d.year,
            precision=Precision.DAY,
            month=d.month,
            day=d.day,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_storage(self) -> str:
        """Encode to the lexicographically-sortable DB representation."""
        mm = self.month or 1
        dd = self.day or 1
        prefix = f"{self.year:04d}-{mm:02d}-{dd:02d}"
        if self.precision is Precision.SEASON:
            return f"{prefix}:season:{self.season}"
        return f"{prefix}:{self.precision}"

    @classmethod
    def from_storage(cls, raw: str) -> FuzzyDate:
        """Inverse of ``to_storage``."""
        date_part, _, tail = raw.partition(":")
        y, m, d = date_part.split("-")
        year, month, day = int(y), int(m), int(d)

        precision_token, _, rest = tail.partition(":")
        precision = Precision(precision_token)

        if precision is Precision.YEAR:
            return cls(year=year, precision=precision)
        if precision is Precision.SEASON:
            return cls(
                year=year,
                precision=precision,
                month=month,
                season=rest or SEASON_LABELS.get(month),
            )
        if precision is Precision.MONTH:
            return cls(year=year, precision=precision, month=month)
        return cls(year=year, precision=precision, month=month, day=day)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        if self.precision is Precision.YEAR:
            return str(self.year)
        if self.precision is Precision.SEASON:
            return f"{(self.season or '').title()} {self.year}"
        if self.precision is Precision.MONTH:
            month_name = dt.date(self.year, self.month or 1, 1).strftime("%B")
            return f"{month_name} {self.year}"
        assert self.day is not None
        return dt.date(self.year, self.month or 1, self.day).strftime("%-d %B %Y")


# ---------------------------------------------------------------------------
# The model field
# ---------------------------------------------------------------------------


class FuzzyDateField(models.CharField):
    """CharField-backed field that materialises as ``FuzzyDate`` objects.

    Why CharField and not two columns? Because the three hooks
    (``from_db_value`` / ``to_python`` / ``get_prep_value``) are the
    interesting shape of a custom field. Splitting into a date + precision
    pair would work but wouldn't teach the pattern.
    """

    description = "A historical date with declared precision"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 30)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        # Drop the max_length we injected so migrations don't drift if we
        # ever bump the default.
        kwargs.pop("max_length", None)
        return name, path, args, kwargs

    # DB → Python. Called once per row per query.
    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return FuzzyDate.from_storage(value)

    # Deserialising from forms / fixtures / explicit assignments.
    def to_python(self, value: Any) -> FuzzyDate | None:
        if value is None or isinstance(value, FuzzyDate):
            return value
        if isinstance(value, str):
            try:
                return FuzzyDate.from_storage(value)
            except Exception as e:  # noqa: BLE001
                raise exceptions.ValidationError(
                    f"cannot parse FuzzyDate from {value!r}"
                ) from e
        raise exceptions.ValidationError(
            f"cannot convert {type(value).__name__} to FuzzyDate"
        )

    # Python → DB. Called on every save.
    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, FuzzyDate):
            return value.to_storage()
        # Allow raw storage strings for direct queries / bulk inserts.
        if isinstance(value, str):
            return value
        raise TypeError(f"FuzzyDateField expects FuzzyDate, got {type(value).__name__}")

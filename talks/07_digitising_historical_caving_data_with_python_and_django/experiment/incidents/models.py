"""
Three models, one per pattern the talk highlights:

* ``Incident`` — the messy record, with a mix of raw OCR input columns and
  structured output columns populated by the pipeline.
* ``Location`` — a tree (``treebeard.MP_Node``) so an incident can attach at
  whatever granularity the source text provides: Country / State / Region /
  Cave. "Arizona" is a valid location, and so is "Carlsbad Caverns".
* ``OperationRun`` — one row per (incident, processing step). Records
  ``status``, ``error_message``, and timestamps. This is what makes the
  pipeline rerunnable: to redo a step you delete its row and run again.
"""

from django.db import models
from treebeard.mp_tree import MP_Node

from incidents.fields import FuzzyDateField


class LocationLevel(models.TextChoices):
    COUNTRY = "country", "Country"
    STATE = "state", "State / Province"
    REGION = "region", "Region"
    CAVE = "cave", "Cave"


class Location(MP_Node):
    """Tree-structured location with fuzzy depth.

    ``MP_Node`` is treebeard's Materialized Path implementation — each node
    stores its path as a compact string, which makes ancestor/descendant
    queries cheap without CTE recursion.

    The talk's key insight: the source data doesn't always reach a specific
    cave. "Arizona Nevada" is just two state-level nodes. A flat
    (country, state, region, cave) set of columns can't represent that
    without a lot of nullable columns and validation code.
    """

    name = models.CharField(max_length=100)
    level = models.CharField(max_length=20, choices=LocationLevel.choices)

    # Alphabetical order within each parent when listed by the admin/API.
    node_order_by = ["name"]

    def __str__(self) -> str:
        # Breadcrumb from root to here: "USA → New Mexico → Carlsbad Caverns"
        ancestors = list(self.get_ancestors()) + [self]
        return " → ".join(a.name for a in ancestors)


class IncidentSeverity(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    MINOR = "minor", "Minor"
    INJURY = "injury", "Injury"
    RESCUE = "rescue", "Rescue"
    FATAL = "fatal", "Fatal"


class Incident(models.Model):
    """One caving accident report, at various stages of refinement."""

    # Raw inputs — what the OCR / LLM-extraction step produced.
    raw_text = models.TextField()
    raw_date_text = models.CharField(max_length=100, blank=True)
    raw_location_text = models.CharField(max_length=200, blank=True)

    # Structured outputs — populated by pipeline operations.
    cleaned_text = models.TextField(blank=True)
    occurred_at = FuzzyDateField(null=True, blank=True)
    location = models.ForeignKey(
        Location,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incidents",
    )
    severity = models.CharField(
        max_length=20,
        choices=IncidentSeverity.choices,
        default=IncidentSeverity.UNKNOWN,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Incident #{self.pk} ({self.occurred_at or 'undated'})"


class OperationStatus(models.TextChoices):
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class OperationRun(models.Model):
    """Audit record of one processing step applied to one incident.

    The ``unique_together`` means "latest outcome wins" — to rerun a step
    you delete its row. This is the simplest scheme that still lets a later
    step check `OperationRun.objects.filter(incident=..., operation_name=...,
    status=SUCCESS).exists()` as a prerequisite.
    """

    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="operations",
    )
    operation_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=OperationStatus.choices)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("incident", "operation_name")]
        ordering = ["incident_id", "operation_name"]

    def __str__(self) -> str:
        return f"{self.operation_name} on #{self.incident_id} [{self.status}]"

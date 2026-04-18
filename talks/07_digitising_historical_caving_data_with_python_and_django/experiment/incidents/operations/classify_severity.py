"""
ClassifySeverity — simple keyword classifier.

In the real pipeline an LLM would categorise the report. Here a short
keyword table is enough to demonstrate a step that reads the *cleaned*
text (so it depends on ``FakeLLMRewrite``) and writes a structured field.
"""

from __future__ import annotations

from incidents.models import Incident, IncidentSeverity
from incidents.operations.base import Operation, register
from incidents.operations.fake_llm_rewrite import FakeLLMRewrite


# Checked in order — first match wins. Upper severities come first so
# "fatality during rescue" is classified as FATAL, not RESCUE.
KEYWORDS: list[tuple[str, IncidentSeverity]] = [
    ("fatal", IncidentSeverity.FATAL),
    ("died", IncidentSeverity.FATAL),
    ("death", IncidentSeverity.FATAL),
    ("rescue", IncidentSeverity.RESCUE),
    ("rescued", IncidentSeverity.RESCUE),
    ("broken", IncidentSeverity.INJURY),
    ("injury", IncidentSeverity.INJURY),
    ("injured", IncidentSeverity.INJURY),
    ("minor", IncidentSeverity.MINOR),
]


@register
class ClassifySeverity(Operation):
    label = "classify severity"
    requires = [FakeLLMRewrite]

    def should_run(self, incident: Incident) -> bool:
        return incident.severity == IncidentSeverity.UNKNOWN

    def run(self, incident: Incident) -> None:
        text = incident.cleaned_text.lower()
        for keyword, severity in KEYWORDS:
            if keyword in text:
                incident.severity = severity
                incident.save(update_fields=["severity"])
                return
        # No keyword matched — that's fine, leave as UNKNOWN. We still
        # complete successfully: "unknown" is a valid classification.

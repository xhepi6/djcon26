"""
FakeLLMRewrite — stand-in for Andrew's "ask the LLM to fix OCR noise" step.

The talk uses a real LLM here. We use deterministic regex fixes that
simulate the behaviour: fix repeated whitespace, stitch split words, tidy
punctuation. The *architecture* — a step that reads ``raw_text`` and writes
``cleaned_text`` — is the lesson, not the prompt.
"""

from __future__ import annotations

import re

from incidents.models import Incident
from incidents.operations.base import Operation, register


# A few representative OCR artefacts from actual scanned documents:
# - hyphenated words split across line breaks:     "rap- pel"  → "rappel"
# - collapsed spaces around punctuation:           "cave ,"    → "cave,"
# - stray double whitespace:                       "  "        → " "
# - spelling of "speleological" getting mangled:   "spelo-..." → "speleological"
FIXES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(\w+)-\s+(\w+)"), r"\1\2"),
    (re.compile(r"\s+,"), ","),
    (re.compile(r"\s+\."), "."),
    (re.compile(r"\s{2,}"), " "),
    (re.compile(r"\bspelo\w*", re.I), "speleological"),
]


@register
class FakeLLMRewrite(Operation):
    label = "LLM rewrite (stub)"

    def should_run(self, incident: Incident) -> bool:
        return bool(incident.raw_text) and not incident.cleaned_text

    def run(self, incident: Incident) -> None:
        text = incident.raw_text
        for pattern, replacement in FIXES:
            text = pattern.sub(replacement, text)
        incident.cleaned_text = text.strip()
        incident.save(update_fields=["cleaned_text"])

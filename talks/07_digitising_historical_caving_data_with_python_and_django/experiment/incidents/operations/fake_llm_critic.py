"""
FakeLLMCritic — the self-check pattern from the talk.

Andrew's insight: have a second pass grade the first pass. If the output
still looks bad, mark the step FAILED so a human (or a later iteration)
can decide what to do. The point is not to crash on bad outputs — it's to
*record* them as failures so they surface in the dashboard.

Here, we "grade" the cleaned text from ``FakeLLMRewrite`` with a small set
of heuristics. ``requires`` makes the runner enforce that the rewrite
already succeeded.
"""

from __future__ import annotations

import re

from incidents.models import Incident
from incidents.operations.base import Operation, register
from incidents.operations.fake_llm_rewrite import FakeLLMRewrite


# Artefacts a clean rewrite should not contain. Note the last pattern —
# "???" is how many OCR engines render unreadable glyphs. The rewrite step
# doesn't (and shouldn't) silently delete them because that would hide
# content loss. The critic's job is to flag the incident as FAILED so a
# human or a later step decides what to do. That's the whole point of
# having a separate grading pass.
SUSPICIOUS = [
    re.compile(r"\s{2,}"),           # leftover double whitespace
    re.compile(r"\w-\s+\w"),         # still-hyphenated line break
    re.compile(r"\s[,.]"),           # space before punctuation
    re.compile(r"\?{2,}"),           # unreadable-glyph placeholder
]


@register
class FakeLLMCritic(Operation):
    label = "LLM critic (stub)"
    requires = [FakeLLMRewrite]

    def run(self, incident: Incident) -> None:
        text = incident.cleaned_text
        problems = [p.pattern for p in SUSPICIOUS if p.search(text)]
        if problems:
            # Signal FAILED by raising. The runner records the message.
            raise ValueError(
                "cleaned_text still contains: " + ", ".join(problems)
            )

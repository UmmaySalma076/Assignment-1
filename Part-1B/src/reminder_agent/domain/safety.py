"""Conservative deterministic screening for explicit disallowed intent."""

from __future__ import annotations

import re

from reminder_agent.contracts.models import RefusalResponse

PATTERNS = (
    (
        "self_harm",
        re.compile(
            r"\b(?:kill|hurt|harm)\s+(?:myself|himself|herself|themselves)\b|\bsuicid",
            re.I,
        ),
    ),
    ("imminent_harm", re.compile(r"\b(?:kill|hurt|harm)\s+(?:him|her|them|someone)\b", re.I)),
    (
        "violence",
        re.compile(
            r"\b(?:attack|shoot|stab|bomb|assault|poison)\b|"
            r"\b(?:punch|beat|hit)\s+(?:him|her|them|someone|the person)\b",
            re.I,
        ),
    ),
    (
        "sensitive_personal_information",
        re.compile(
            r"\b(?:dox|expose|publish|leak|share|post)\b.{0,60}"
            r"\b(?:home\s+address|address|ssn|social security|password|private information)\b",
            re.I,
        ),
    ),
)


def refusal_for_request(text: str) -> RefusalResponse | None:
    for category, pattern in PATTERNS:
        if pattern.search(text):
            return RefusalResponse(
                outcome="refusal",
                category=category,
                message="I can’t help plan or facilitate harm or misuse of private information.",
            )
    return None

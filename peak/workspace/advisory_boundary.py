"""The Peak Advisory Engagement Boundary (Phase 217; Contract C21).

Default Peak engagement work is advisory and improvement-oriented. It may examine workflows,
records, policies, controls, physical operations, employee practices, operational consistency and
supporting evidence, to understand how the business operates and to identify practical
improvements. It is never framed, generated, executed, scored, labelled or reported as an audit, a
compliance test, certification, assurance, a finding of non-compliance or a control deficiency
determination. Peak has no governed audit capability, so no engagement is ever an exception.

This module is the enforcement point for the words that define work: the framing of a roadmap item,
an engagement phase and a guided task. Consultant notes and task records are **not** filtered: they
record what actually happened, which can legitimately mention the client's own auditor. The
canonical text is docs/ADVISORY_ENGAGEMENT_BOUNDARY.md.

Pure functions; no database, no environment, no model call.
"""

from __future__ import annotations

import re
from typing import Iterable, List

#: Peak has no governed audit capability. A future one would be a separate, explicitly created
#: engagement type with its own authority; this flag exists so that is a deliberate change.
GOVERNED_AUDIT_CAPABILITY_AVAILABLE = False

#: Terms that frame work as audit, compliance, certification or assurance. Matched
#: case-insensitively on word boundaries; each pattern names the concept it stands for.
PROHIBITED_FRAMING = (
    (re.compile(r"\baudit\w*", re.IGNORECASE), "audit"),
    (re.compile(r"\b(?:non[-\s]?)?complian\w*", re.IGNORECASE), "compliance"),
    (re.compile(r"\bcertif\w*", re.IGNORECASE), "certification"),
    (re.compile(r"\bassurance\b", re.IGNORECASE), "assurance"),
    (re.compile(r"\battest\w*", re.IGNORECASE), "attestation"),
    (re.compile(r"\bdeficienc\w*", re.IGNORECASE), "control deficiency"),
    (re.compile(r"\bmaterial\s+weakness\w*", re.IGNORECASE), "material weakness"),
    (re.compile(r"\bviolation\w*", re.IGNORECASE), "violation"),
)

#: The language normal Peak work uses instead.
ADVISORY_VOCABULARY = ("observed workflow", "variance", "friction", "inconsistency", "rework",
                       "delay", "error", "operational impact", "improvement opportunity",
                       "recommended process change")

BOUNDARY_MESSAGE = (
    "Peak engagement work is advisory and improvement-oriented. Describe it as observed workflow, "
    "variance, friction, inconsistency, rework, delay, error, operational impact or an "
    "improvement opportunity, not as {concept}.")


def _texts(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _texts(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)


def framing_violations(value) -> List[str]:
    """The prohibited concepts ``value`` (text, or a list/dict of text) uses, in a fixed order."""
    found = []
    for text in _texts(value):
        for pattern, concept in PROHIBITED_FRAMING:
            if pattern.search(text) and concept not in found:
                found.append(concept)
    return [c for _, c in PROHIBITED_FRAMING if c in found]


def first_violation(values: dict):
    """``(field, concept)`` for the first framing field that crosses the boundary, else None."""
    for field in sorted(values):
        concepts = framing_violations(values[field])
        if concepts:
            return field, concepts[0]
    return None

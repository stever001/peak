"""Peak Method phase templates (Phase 217): sellable follow-on phases and their guided work plans.

A template is deterministic Peak Method content, not a model output. It says when a phase may be
worth suggesting (the discovery categories its grounding observations must come from), how to frame
it, and the ordered guided tasks that tell a consultant what to do, observe, ask and record.

**Suggestions rest on consultant observations only.** A template is suggested for an engagement
when at least one discovery observation falls in one of its trigger categories (through the
question that prompted it, or the observation's own category). Interview answers never trigger a
suggestion: an answer guides discovery, it does not establish anything (Phase 216; Contract C4).
A suggestion is advisory; it becomes a roadmap item only when a consultant adds it, and authorized
work only when the client separately agrees to the phase.

Every framing string here stays inside the advisory boundary (Contract C21); the Phase 217 harness
checks each one. Templates are Peak-specific on purpose; nothing here is a generic workflow engine.
"""

from __future__ import annotations

from typing import Dict, List

METHOD_VERSION = "peak.method_phases.2026-10.v1"

#: Record kinds a task may suggest (mirrors ``peak.db.models.PHASE_TASK_RECORD_KINDS``).
EVIDENCE_KINDS = ("note", "interview_response", "measurement", "mismatch", "photo",
                  "document_photo", "document")


def _task(key, title, instructions, *, why, observe, evidence, questions, expected,
          required=True, requires_record=True, depends_on=(), condition=None):
    return {"key": key, "title": title, "instructions": instructions, "why_it_matters": why,
            "what_to_observe": observe, "suggested_evidence": list(evidence),
            "follow_up_questions": list(questions), "expected_result": expected,
            "required": required, "requires_record": requires_record,
            "depends_on": list(depends_on), "condition": condition}


TEMPLATES: List[dict] = [
    {
        "key": "receiving_accuracy",
        "title": "Receiving Accuracy and Workflow Improvement",
        "trigger_categories": ("Receiving and storage",),
        "problem_framing": (
            "Discovery describes receiving discrepancies and receiving practices that vary by "
            "person or shift, so on-hand quantities may drift from the start of the inventory "
            "flow."),
        "rationale": (
            "Receiving is where stock first enters the record. Variance introduced here carries "
            "into every later count, pick and replenishment decision, and is cheaper to reduce at "
            "the dock than to chase downstream."),
        "expected_outcome": (
            "A documented picture of how receiving actually works, where it produces variance, "
            "rework or delay, and a set of practical, recommended process changes the client can "
            "adopt."),
        "scope_summary": (
            "Observe the receiving workflow, review a sample of purchase orders against packing "
            "slips, record mismatches and how staff resolve them, interview receiving personnel, "
            "and identify recurring friction and rework patterns."),
        "tasks": [
            _task("observe_receiving", "Observe the receiving workflow",
                  "Watch at least one full receipt from truck arrival to put-away. Note each step, "
                  "who performs it, what document or screen they use, and where goods wait.",
                  why="The observed workflow is the baseline every later step is compared with; "
                      "what people describe and what happens often differ.",
                  observe="Order of steps, hand-offs, where counts happen (or do not), staging "
                          "areas, labelling, and any step skipped under time pressure.",
                  evidence=("note", "photo", "measurement"),
                  questions=("What happens when the truck arrives before the paperwork?",
                             "Who decides where received goods are put away?"),
                  expected="A step-by-step note of the observed receiving workflow, with timings "
                           "where useful."),
            _task("po_packing_slip_sample", "Review a sample of purchase orders and packing slips",
                  "Select a sample of recent receipts. For each, compare the purchase order with "
                  "the corresponding packing slip (and the received quantity, where recorded). "
                  "Record every mismatch as its own mismatch record.",
                  why="Mismatches between what was ordered, shipped and recorded show where "
                      "receiving variance comes from and how often it occurs.",
                  observe="Quantity, item, unit-of-measure and substitution differences; slips "
                          "missing or unsigned; receipts entered before goods were checked.",
                  evidence=("document_photo", "document", "mismatch", "note"),
                  questions=("How was this sample chosen, and is it typical?",
                             "Where are packing slips kept after receiving?"),
                  expected="One mismatch record per discrepancy (reference, expected, observed), "
                           "plus a note of the sample size and how it was chosen."),
            _task("discrepancy_handling", "Record how staff resolve the mismatches found",
                  "For the mismatches recorded in the sample, find out what staff did about each: "
                  "who noticed, who was told, what was changed in the record, and how long it "
                  "took.",
                  why="How discrepancies are handled decides whether variance is corrected, "
                      "hidden or repeated.",
                  observe="Whether resolution is consistent between people; informal workarounds; "
                          "rework and delay caused by each discrepancy.",
                  evidence=("note", "interview_response", "document_photo"),
                  questions=("What do you do when the slip and the box disagree?",
                             "Who is told about a short or over shipment, and how?"),
                  expected="A note per resolution pattern, linked to the mismatches it covers.",
                  depends_on=("po_packing_slip_sample",),
                  condition=("po_packing_slip_sample", "mismatch")),
            _task("receiving_interviews", "Interview receiving personnel",
                  "Interview the people who receive goods, using the clarification questions "
                  "below and anything the observation raised. Record each answer as an interview "
                  "response.",
                  why="Interviews explain the reasons behind what was observed and surface "
                      "friction that a single observation can miss.",
                  observe="Differences between people or shifts, training gaps, and steps people "
                          "consider unnecessary or unclear.",
                  evidence=("interview_response", "note"),
                  questions=("Walk me through what you do when a delivery arrives.",
                             "What slows receiving down most often?",
                             "What would you change about how receiving works?"),
                  expected="Interview responses from the receiving staff, attributed by role.",
                  depends_on=("observe_receiving",)),
            _task("receiving_layout_photos", "Photograph the receiving layout and labelling",
                  "Where it helps explain the workflow, photograph the receiving area, staging, "
                  "shelving and labels. Until photo capture is available, record a note that "
                  "describes each photograph and where it is kept.",
                  why="Physical layout and labelling often explain delay and put-away variance "
                      "better than a description can.",
                  observe="Congestion, unlabelled staging, mixed items, and distance to storage.",
                  evidence=("photo", "note"),
                  questions=(),
                  expected="Photographs (or notes describing them) of the relevant areas.",
                  required=False, requires_record=False),
            _task("receiving_friction_patterns", "Identify recurring friction and rework patterns",
                  "Using only what was recorded in the earlier tasks, note the patterns that "
                  "recur: where variance, rework or delay keeps happening, and the operational "
                  "impact of each.",
                  why="Patterns grounded in recorded work are what the later synthesis and "
                      "recommendations rest on.",
                  observe="Patterns supported by more than one record; conflicting records that "
                          "need clarification before synthesis.",
                  evidence=("note",),
                  questions=("Do the interview responses agree with what was observed?",),
                  expected="A note per pattern, citing the records it rests on.",
                  depends_on=("observe_receiving", "po_packing_slip_sample",
                              "discrepancy_handling", "receiving_interviews")),
        ],
    },
    {
        "key": "count_adjustment_practice",
        "title": "Inventory Count and Adjustment Practice Improvement",
        "trigger_categories": ("Counting and adjustments", "Record reliability"),
        "problem_framing": (
            "Discovery describes inventory records that staff do not fully rely on, and counts or "
            "adjustments that are performed inconsistently."),
        "rationale": (
            "How counts are taken and how adjustments are made decides whether record variance is "
            "understood and reduced, or simply overwritten."),
        "expected_outcome": (
            "A clear picture of current count and adjustment practice, the variance and rework it "
            "produces, and recommended process changes."),
        "scope_summary": (
            "Observe a count, review a sample of recent adjustments and their stated reasons, "
            "interview the people who count and adjust, and identify recurring patterns."),
        "tasks": [
            _task("observe_count", "Observe an inventory count",
                  "Observe a scheduled or cycle count. Note how locations are chosen, how counts "
                  "are recorded, and what happens when a count differs from the record.",
                  why="The count procedure as performed is the baseline for every adjustment.",
                  observe="Blind or guided counting, recounts, who resolves differences, timing.",
                  evidence=("note", "measurement", "document_photo"),
                  questions=("What happens when your count does not match the system?",),
                  expected="A note of the observed count procedure."),
            _task("adjustment_sample", "Review a sample of recent adjustments",
                  "Select a sample of recent inventory adjustments. For each, compare the count "
                  "sheet or source with the adjustment entered, and the reason given. Record each "
                  "difference as a mismatch record.",
                  why="Adjustments without a traceable source or reason make variance invisible.",
                  observe="Missing reasons, round-number adjustments, repeated adjustments to the "
                          "same item, adjustments entered long after the count.",
                  evidence=("document_photo", "document", "mismatch", "note"),
                  questions=("Who can enter an adjustment, and who looks at them afterwards?",),
                  expected="Mismatch records for differences found, plus a note of the sample."),
            _task("count_interviews", "Interview the people who count and adjust",
                  "Interview counters and whoever enters or reviews adjustments, using the "
                  "questions below. Record each answer as an interview response.",
                  why="Interviews explain why practice differs from the stated procedure.",
                  observe="Differences between people, pressure to close counts quickly, "
                          "knowledge held by one person.",
                  evidence=("interview_response",),
                  questions=("How do you decide an adjustment is right?",
                             "What makes counting difficult here?"),
                  expected="Interview responses attributed by role.",
                  depends_on=("observe_count",)),
            _task("count_patterns", "Identify recurring count and adjustment patterns",
                  "Using only the recorded work, note recurring patterns of variance, rework or "
                  "delay and their operational impact.",
                  why="Grounded patterns are what later synthesis rests on.",
                  observe="Patterns supported by more than one record; conflicting records.",
                  evidence=("note",),
                  questions=(),
                  expected="A note per pattern, citing the records it rests on.",
                  depends_on=("observe_count", "adjustment_sample", "count_interviews")),
        ],
    },
]

BY_KEY: Dict[str, dict] = {t["key"]: t for t in TEMPLATES}


def template(key: str) -> dict:
    return BY_KEY[key]


def _norm(text) -> str:
    return text.strip().lower() if isinstance(text, str) else ""


def matching_observation_ids(tmpl: dict, observations: List[dict], question_categories: dict):
    """Ids of the observations that fall in one of ``tmpl``'s trigger categories, in input order.

    ``observations`` are ``{"id", "category", "question_id"}`` dicts; ``question_categories`` maps a
    question id to its category. An observation matches through its prompting question's category,
    or its own category. Nothing else is read.
    """
    triggers = {_norm(c) for c in tmpl["trigger_categories"]}
    return [o["id"] for o in observations
            if _norm(question_categories.get(o.get("question_id"))) in triggers
            or _norm(o.get("category")) in triggers]


def suggest(observations: List[dict], question_categories: dict, on_roadmap=()) -> List[dict]:
    """Deterministic roadmap suggestions: one per template with grounding observations.

    Templates already on the roadmap (``on_roadmap``: template keys of live items) are left out.
    Each suggestion cites the observations it rests on. No model, no score, no ranking: templates
    keep their catalogue order.
    """
    out = []
    for tmpl in TEMPLATES:
        if tmpl["key"] in set(on_roadmap):
            continue
        ids = matching_observation_ids(tmpl, observations, question_categories)
        if not ids:
            continue
        out.append({
            "template_key": tmpl["key"], "title": tmpl["title"],
            "problem_framing": tmpl["problem_framing"], "rationale": tmpl["rationale"],
            "expected_outcome": tmpl["expected_outcome"], "source_observation_ids": ids,
            "grounding": (f"{len(ids)} consultant observation{'s' if len(ids) != 1 else ''} "
                          f"recorded in discovery about "
                          f"{' / '.join(c.lower() for c in tmpl['trigger_categories'])}."),
            "method_version": METHOD_VERSION,
        })
    return out


def catalogue() -> List[dict]:
    """The templates as a consultant chooses between them (Phase 219): read-only, in catalogue order.

    Framing and task outline only; trigger categories and task guidance stay with the template and
    reach a phase only when its tasks are added.
    """
    return [{
        "template_key": t["key"], "title": t["title"], "problem_framing": t["problem_framing"],
        "expected_outcome": t["expected_outcome"], "scope_summary": t["scope_summary"],
        "method_version": METHOD_VERSION,
        "tasks": [{"sequence": n, "title": s["title"], "required": s["required"]}
                  for n, s in enumerate(t["tasks"], start=1)],
    } for t in TEMPLATES]

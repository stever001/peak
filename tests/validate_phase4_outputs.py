#!/usr/bin/env python3
"""Phase 4 example-output inventory check.

Lightweight, stdlib-only. Confirms that each required sample-output artifact under
examples/outputs/ exists and contains its expected section markers. This is a
STRUCTURAL/presence check only -- it does NOT assess report quality or semantics.

Exit status:
  0  -> all required output files present and contain expected sections
  1  -> a required file is missing or is missing expected sections
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "examples", "outputs")

# Required artifacts and the section markers each must contain. Markers are matched
# case-insensitively as substrings of the file text, so light wording changes do not
# break the check. This is presence-only, not a quality judgement.
REQUIRED_OUTPUTS = {
    "discovery-plan.alpha.example.md": [
        "assessment objective",
        "interview plan",
        "walk-around checklist",
        "document / data request",
        "risks to validate",
        "first-billing-tranche objective",
    ],
    "evidence-findings.alpha.example.md": [
        "process",
        "system",
        "control",
        "data quality",
        "operational risk",
    ],
    "initial-assessment-report.alpha.example.md": [
        "executive summary",
        "current-state findings",
        "risk / impact",
        "quick wins",
        "priority recommendations",
        "next-step framing",
    ],
    "next-phase-proposal.alpha.example.md": [
        "recommended scope",
        "workstreams",
        "deliverables",
        "timeline assumptions",
        "client responsibilities",
        "success measures",
        "commercial rationale",
        "pricing",
    ],
    "qa-review.alpha.example.md": [
        "unsupported claims",
        "missing evidence",
        "contradictions",
        "weak recommendations",
        "report-readiness",
        "required fixes",
    ],
    "engagement-lessons.alpha.example.md": [
        "reusable patterns",
        "checklist improvements",
        "prompt improvements",
        "schema gaps",
        "candidate internal knowledge capsules",
        "follow-up actions",
    ],
}

# Every artifact must cite at least one packet evidence id.
EVIDENCE_TOKEN = "evid_alpha_"

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("Peak Phase 4 example-output inventory check")
    print("=" * 43)

    failures: list[str] = []
    checks = 0

    for name, sections in REQUIRED_OUTPUTS.items():
        checks += 1
        path = os.path.join(OUTPUT_DIR, name)
        if not os.path.isfile(path):
            failures.append(f"{name}: MISSING")
            print(f"  [{FAIL}] {name}: file not found")
            continue

        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().lower()

        missing = [s for s in sections if s not in text]
        problems = []
        if missing:
            problems.append("missing sections: " + ", ".join(missing))
        if EVIDENCE_TOKEN not in text:
            problems.append("no packet evidence id cited (expected 'evid_alpha_...')")

        if problems:
            failures.append(f"{name}: " + "; ".join(problems))
            print(f"  [{FAIL}] {name}: " + "; ".join(problems))
        else:
            print(f"  [{PASS}] {name}: all {len(sections)} sections + evidence cited")

    print("\n" + "=" * 43)
    print("Summary")
    print(f"  output files checked : {checks}")
    print(f"  failures             : {len(failures)}")

    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

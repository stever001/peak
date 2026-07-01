#!/usr/bin/env python3
"""Phase 3 prompt-contract inventory check.

Lightweight, stdlib-only. Confirms that every required prompt contract exists and
contains all ten required section headings, plus a reusable prompt body (a fenced
code block). It does NOT judge prompt quality or execute any model.

Exit status:
  0  -> all required prompt files present and well-formed
  1  -> a required file is missing or is missing required sections
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_DIR = os.path.join(REPO_ROOT, "prompts")

# Required contract files (relative to prompts/).
REQUIRED_PROMPTS = [
    "intake/normalize-client-intake.prompt.md",
    "discovery/generate-discovery-plan.prompt.md",
    "evidence/extract-evidence-findings.prompt.md",
    "reporting/draft-initial-assessment-report.prompt.md",
    "proposal/generate-next-phase-proposal.prompt.md",
    "qa/review-assessment-packet.prompt.md",
    "learning/extract-engagement-lessons.prompt.md",
]

# Required section headings, matched case-insensitively as substrings of the
# markdown heading lines. Kept as concepts, not exact strings, so light wording
# changes to a heading do not break the check.
REQUIRED_SECTIONS = [
    "Purpose",
    "Intended user",
    "Required input",
    "Expected output",
    "Grounding rules",
    "Evidence rules",
    "Non-goals",
    "Output format",
    "Quality checks",
    "Reusable prompt body",
]

PASS = "PASS"
FAIL = "FAIL"


def heading_lines(text: str) -> list[str]:
    return [ln.strip().lower() for ln in text.splitlines() if ln.lstrip().startswith("#")]


def main() -> int:
    print("Peak Phase 3 prompt-contract inventory check")
    print("=" * 44)

    failures: list[str] = []
    checks = 0

    for rel in REQUIRED_PROMPTS:
        checks += 1
        path = os.path.join(PROMPT_DIR, rel)
        if not os.path.isfile(path):
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")
            continue

        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()

        headings = heading_lines(text)
        missing = [
            section
            for section in REQUIRED_SECTIONS
            if not any(section.lower() in h for h in headings)
        ]
        # The reusable body must include a fenced code block to copy/paste.
        has_body = "```" in text

        problems = []
        if missing:
            problems.append("missing sections: " + ", ".join(missing))
        if not has_body:
            problems.append("no fenced code block for the reusable prompt body")

        if problems:
            failures.append(f"{rel}: " + "; ".join(problems))
            print(f"  [{FAIL}] {rel}: " + "; ".join(problems))
        else:
            print(f"  [{PASS}] {rel}: all {len(REQUIRED_SECTIONS)} sections + body")

    print("\n" + "=" * 44)
    print("Summary")
    print(f"  prompt files checked : {checks}")
    print(f"  failures             : {len(failures)}")

    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

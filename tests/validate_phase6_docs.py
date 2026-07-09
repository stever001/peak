#!/usr/bin/env python3
"""Phase 6 consultant-guide doc check.

Lightweight, stdlib-only. Confirms that docs/CONSULTANT_WORKFLOW.md exists and
contains the required section headings. Presence/structure only -- it does not judge
the prose.

Exit status:
  0  -> guide present and contains all required sections
  1  -> guide missing or missing required sections
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDE = os.path.join(REPO_ROOT, "docs", "CONSULTANT_WORKFLOW.md")

# Required section concepts, matched case-insensitively as substrings of the guide.
REQUIRED_SECTIONS = [
    "purpose and scope",
    "end-to-end workflow",
    "commands",
    "file map",
    "consultant rules",
    "qa gate",
    "lessons capture",
    "phase boundary",
]

# The guide must keep the honesty disclaimers intact.
REQUIRED_PHRASES = [
    "human-in-the-loop",
    "does not",          # e.g. "does not call an LLM..."
    "agentnet",          # discussed as intended-only
]

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("Peak Phase 6 consultant-guide doc check")
    print("=" * 39)

    if not os.path.isfile(GUIDE):
        print(f"  [{FAIL}] docs/CONSULTANT_WORKFLOW.md: file not found")
        print(f"\nRESULT: {FAIL} (1 issue)")
        return 1
    print(f"  [{PASS}] docs/CONSULTANT_WORKFLOW.md exists")

    with open(GUIDE, "r", encoding="utf-8") as fh:
        text = fh.read().lower()

    failures: list[str] = []

    missing_sections = [s for s in REQUIRED_SECTIONS if s not in text]
    if missing_sections:
        failures.append("missing sections: " + ", ".join(missing_sections))
        print(f"  [{FAIL}] missing sections: " + ", ".join(missing_sections))
    else:
        print(f"  [{PASS}] all {len(REQUIRED_SECTIONS)} required sections present")

    missing_phrases = [p for p in REQUIRED_PHRASES if p not in text]
    if missing_phrases:
        failures.append("missing phrases: " + ", ".join(missing_phrases))
        print(f"  [{FAIL}] missing phrases: " + ", ".join(missing_phrases))
    else:
        print(f"  [{PASS}] honesty/scope phrases present")

    print("\n" + "=" * 39)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

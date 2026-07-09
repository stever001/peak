#!/usr/bin/env python3
"""Phase 7 data-handling policy & redaction doc check.

Lightweight, stdlib-only. Confirms the policy docs and redacted examples exist and
contain their required section headings / phrases. Presence/structure only -- it does
not judge the prose, and it does not attempt to detect real client data.

Exit status:
  0  -> all required files present and contain required sections/phrases
  1  -> a required file is missing or is missing required content
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# path (relative to repo root) -> list of required lowercase substrings
REQUIRED_FILES = {
    "docs/DATA_HANDLING_POLICY.md": [
        "purpose and scope",
        "internal-only",
        "no real client data",
        "secrets",
        "sensitive_data_flag",
        "retention",
        "human review",
        "agentnet",
        "future work",
    ],
    "docs/REDACTION_GUIDE.md": [
        "redaction patterns",
        "client_alpha",
        "vendor_alpha",
        "[redacted_pricing]",
        "before / after",
        "checklist",
    ],
    "examples/redacted/README.md": [
        "fictional",
        "redact",
    ],
    "examples/redacted/redacted-intake-notes.example.md": [
        "client_alpha",
        "redact",
    ],
    "examples/redacted/redacted-visual-observation-notes.example.md": [
        "site_alpha",
        "redact",
    ],
    "examples/redacted/redacted-interview-notes.example.md": [
        "warehouse_lead_alpha",
        "redact",
    ],
}

PASS = "PASS"
FAIL = "FAIL"


def main() -> int:
    print("Peak Phase 7 data-handling policy check")
    print("=" * 39)

    failures: list[str] = []
    checks = 0

    for rel, needles in REQUIRED_FILES.items():
        checks += 1
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(path):
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")
            continue
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read().lower()
        missing = [n for n in needles if n not in text]
        if missing:
            failures.append(f"{rel}: missing " + ", ".join(missing))
            print(f"  [{FAIL}] {rel}: missing " + ", ".join(missing))
        else:
            print(f"  [{PASS}] {rel}: all {len(needles)} required markers present")

    print("\n" + "=" * 39)
    print("Summary")
    print(f"  files checked : {checks}")
    print(f"  failures      : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

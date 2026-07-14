#!/usr/bin/env python3
"""Phase 8 controlled-data architecture doc check.

Lightweight, stdlib-only. Confirms the Phase 8 architecture docs exist with their
required markers, that the repo stays source-only (no data artifacts), and that AgentNet
is not described as implemented anywhere.

Checks:
  1. Required Phase 8 docs exist and contain their required headings/phrases.
  2. Source-only discipline: no `examples/` dir, no `docs/REDACTION_GUIDE.md`, and no
     committed `*.example.*` / sample-output artifacts.
  3. Source-only policy phrase present (README).
  4. AgentNet is not described as implemented (no "AgentNet ... integrated/complete"
     without a "not"/"intended"/"future" qualifier on the same line).

Exit status:
  0  -> all checks passed
  1  -> a doc/marker is missing, a data artifact exists, or AgentNet is over-claimed
"""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_DOCS = {
    "docs/CONTROLLED_DATA_ARCHITECTURE.md": [
        "source-only",
        "controlled engagement database",
        "private resolver capsules",
        "no client data in git",
        "synthetic runtime fixtures only",
        "data classification",
        "prohibited_repo_data",
        "intended future",
    ],
    "docs/RESOLVER_CAPSULE_ARCHITECTURE.md": [
        "resolver capsule",
        "capsule_scope",
        "peak_methodology",
        "client_private",
        "fixture_test",
        "owner_id",
        "lifecycle_status",
        "governance approval",
        "intended future",
    ],
    "docs/ENGAGEMENT_DATA_MODEL.md": [
        "engagement data model",
        "financialimpactestimate",
        "resolvercapsulerecord",
        "sourcesystemreference",
        "not a database migration",
        "no invented roi",
        "no financial numbers in repo",
    ],
    "docs/SOURCE_SYSTEM_CAPSULIZATION.md": [
        "capsulization",
        "telemetry",
        "operational logs",
        "authorization scope",
        "review status",
        "intended future",
    ],
}

FORBIDDEN_PATHS = ["examples", "docs/REDACTION_GUIDE.md"]

SOURCE_ONLY_MARKER = ("README.md", "source assets only")

# AgentNet over-claim scan. Flag only explicit *completion* claims — describing a
# future AgentNet integration phase is fine; asserting it is done/live/integrated is not.
SCAN_ROOTS = ["README.md", "docs", "schemas", "tools", "tests", "prompts"]
SCAN_EXTS = (".md", ".py", ".json")
SCAN_SKIP = {
    os.path.abspath(__file__),
    # Sibling guard that legitimately contains the over-claim phrases to detect them.
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase9_governance.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase10_database_plan.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase11_db_scaffold.py")),
}
AGENTNET_OVERCLAIM_PHRASES = (
    "agentnet is integrated",
    "agentnet integration is complete",
    "agentnet integration complete",
    "agentnet integration is done",
    "agentnet is live",
    "agentnet grounding is live",
    "fully integrated with agentnet",
    "agentnet is now integrated",
)

PASS = "PASS"
FAIL = "FAIL"


def read(rel):
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def iter_scan_files():
    for root in SCAN_ROOTS:
        p = os.path.join(REPO_ROOT, root)
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for dp, _, files in os.walk(p):
                for f in files:
                    fp = os.path.join(dp, f)
                    if fp.endswith(SCAN_EXTS):
                        yield fp


def find_forbidden_globs():
    hits = []
    for dp, _, files in os.walk(REPO_ROOT):
        if ".git" in dp.split(os.sep):
            continue
        for f in files:
            if f.endswith(".example.json") or f.endswith(".example.md") or "redacted" in f:
                hits.append(os.path.relpath(os.path.join(dp, f), REPO_ROOT))
    return hits


def main() -> int:
    print("Peak Phase 8 controlled-data architecture check")
    print("=" * 47)
    failures: list[str] = []

    # 1. Required docs + markers.
    print("\n1. Architecture docs")
    for rel, needles in REQUIRED_DOCS.items():
        path = os.path.join(REPO_ROOT, rel)
        if not os.path.isfile(path):
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")
            continue
        text = read(rel).lower()
        missing = [n for n in needles if n not in text]
        if missing:
            failures.append(f"{rel}: missing " + ", ".join(missing))
            print(f"  [{FAIL}] {rel}: missing " + ", ".join(missing))
        else:
            print(f"  [{PASS}] {rel}: all {len(needles)} markers present")

    # 2. Source-only discipline.
    print("\n2. Source-only discipline (no data artifacts)")
    for rel in FORBIDDEN_PATHS:
        if os.path.exists(os.path.join(REPO_ROOT, rel)):
            failures.append(f"forbidden path exists: {rel}")
            print(f"  [{FAIL}] forbidden path exists: {rel}")
        else:
            print(f"  [{PASS}] absent: {rel}")
    globs = find_forbidden_globs()
    if globs:
        for g in globs:
            failures.append(f"forbidden artifact: {g}")
            print(f"  [{FAIL}] forbidden artifact: {g}")
    else:
        print(f"  [{PASS}] no *.example.* or redacted artifacts found")

    # 3. Source-only policy phrase.
    print("\n3. Source-only policy phrase")
    rel, phrase = SOURCE_ONLY_MARKER
    if phrase in read(rel).lower():
        print(f"  [{PASS}] {rel} states '{phrase}'")
    else:
        failures.append(f"{rel}: missing '{phrase}'")
        print(f"  [{FAIL}] {rel}: missing '{phrase}'")

    # 4. AgentNet not described as implemented (explicit completion claims only).
    print("\n4. AgentNet not described as implemented")
    import re

    offenders = []
    for fp in iter_scan_files():
        if os.path.abspath(fp) in SCAN_SKIP:
            continue
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                normalized = re.sub(r"\s+", " ", fh.read().lower())
        except (OSError, UnicodeDecodeError):
            continue
        negators = ("not", "never", "no ", "cannot", "n't", "without")
        for phrase in AGENTNET_OVERCLAIM_PHRASES:
            start = 0
            while True:
                idx = normalized.find(phrase, start)
                if idx == -1:
                    break
                start = idx + len(phrase)
                window = normalized[max(0, idx - 60):idx]
                if any(n in window for n in negators):
                    continue  # negated policy statement ("no file may claim ..."), not a claim
                offenders.append(f"{os.path.relpath(fp, REPO_ROOT)}: '{phrase}'")
    if offenders:
        for o in offenders:
            failures.append(f"AgentNet over-claim: {o}")
            print(f"  [{FAIL}] AgentNet over-claim at {o}")
    else:
        print(f"  [{PASS}] AgentNet described only as intended/not-integrated")

    print("\n" + "=" * 47)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

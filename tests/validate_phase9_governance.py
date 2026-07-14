#!/usr/bin/env python3
"""Phase 9 governance-state contract check.

Confirms the Phase 9 governance docs and enum-contract schemas are present and correct,
that transition/guardrail language is documented, and that the repo stays source-only.
Uses stdlib plus `jsonschema` (already used elsewhere) for check_schema.

Checks:
  1. Phase 9 docs exist (GOVERNANCE_STATES.md, STATE_TRANSITIONS.md).
  2. Governance schemas pass draft 2020-12 check_schema.
  3. Required enum values are present for all eight state families.
  4. STATE_TRANSITIONS.md contains the key transition arrows and agent guardrails.
  5. Source-only discipline: no examples/, no *.example.*, no stored data artifacts.
  6. AgentNet is not described as implemented.

Exit status:
  0  -> all checks passed
  1  -> a check failed
  2  -> jsonschema is missing
"""

from __future__ import annotations

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_DOCS = ["docs/GOVERNANCE_STATES.md", "docs/STATE_TRANSITIONS.md"]

GOVERNANCE_SCHEMAS = [
    "schemas/governance-state.schema.json",
    "schemas/review-status.schema.json",
    "schemas/authorization-scope.schema.json",
    "schemas/lifecycle-status.schema.json",
]

# family -> (schema file, required enum values)
ENUMS = {
    "AuthorizationScope": ("schemas/authorization-scope.schema.json", [
        "engagement_authorized", "internal_peak_only", "client_private",
        "client_facing_candidate", "client_facing_approved", "methodology_candidate",
        "peak_methodology", "fixture_test", "revoked"]),
    "ReviewStatus": ("schemas/review-status.schema.json", [
        "draft", "needs_review", "consultant_reviewed", "qa_reviewed",
        "approved_internal", "client_facing_approved", "rejected", "superseded",
        "archived"]),
    "LifecycleStatus": ("schemas/lifecycle-status.schema.json", [
        "active", "pending", "draft", "superseded", "revoked", "archived",
        "deleted_reference_only"]),
    "EvidenceStatus": ("schemas/governance-state.schema.json", [
        "collected", "source_labeled", "needs_verification", "verified", "disputed",
        "superseded", "excluded", "archived"]),
    "FinancialImpactStatus": ("schemas/governance-state.schema.json", [
        "not_assessed", "reported", "estimated", "calculated", "finance_review_needed",
        "finance_reviewed", "verified", "rejected", "client_facing_approved"]),
    "ResolverCapsuleStatus": ("schemas/governance-state.schema.json", [
        "draft_capsule", "private_client_capsule", "reviewed_private", "active_private",
        "methodology_candidate", "approved_methodology", "superseded", "revoked",
        "archived"]),
    "SourceSystemAccessStatus": ("schemas/governance-state.schema.json", [
        "not_requested", "requested", "granted", "partial", "denied", "expired",
        "revoked"]),
    "ClientFacingApprovalStatus": ("schemas/governance-state.schema.json", [
        "not_client_facing", "client_facing_candidate", "requires_review",
        "approved_for_client", "rejected_for_client", "withdrawn"]),
}

REQUIRED_ARROWS = [
    "draft -> needs_review -> consultant_reviewed -> qa_reviewed -> approved_internal",
    "approved_internal -> client_facing_candidate -> approved_for_client",
    "collected -> source_labeled -> needs_verification -> verified",
    "calculated -> finance_review_needed -> finance_reviewed -> verified",
    "draft_capsule -> private_client_capsule -> reviewed_private -> active_private",
    "not_requested -> requested",
]

REQUIRED_GUARDRAILS = [
    "may not** mark records `client_facing_approved`",
    "may not** verify financial impact without human review",
    "may not** publish or approve resolver capsules",
    "propose methodology candidates",
    "default to `draft` or `needs_review`",
]

AGENTNET_OVERCLAIM = (
    "agentnet is integrated", "agentnet integration is complete",
    "agentnet integration complete", "agentnet integration is done",
    "agentnet is live", "agentnet grounding is live", "fully integrated with agentnet",
)
AGENTNET_NEGATORS = ("not", "never", "no ", "cannot", "n't", "without")

SCAN_ROOTS = ["README.md", "docs", "schemas", "tools", "tests", "prompts"]
# Sibling guards legitimately contain the over-claim phrases to detect them.
SCAN_SKIP = {
    os.path.abspath(__file__),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase8_architecture.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase10_database_plan.py")),
    os.path.abspath(os.path.join(REPO_ROOT, "tests", "validate_phase11_db_scaffold.py")),
}

PASS, FAIL = "PASS", "FAIL"


def load(rel):
    with open(os.path.join(REPO_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def enum_of(schema: dict, family: str):
    return schema.get("$defs", {}).get(family, {}).get("enum", [])


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
    print("Peak Phase 9 governance-state contract check")
    print("=" * 44)
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("\nERROR: jsonschema required (make install-dev).", file=sys.stderr)
        return 2

    failures: list[str] = []

    # 1. Docs exist.
    print("\n1. Governance docs")
    for rel in REQUIRED_DOCS:
        if os.path.isfile(os.path.join(REPO_ROOT, rel)):
            print(f"  [{PASS}] {rel} exists")
        else:
            failures.append(f"{rel}: MISSING")
            print(f"  [{FAIL}] {rel}: file not found")

    # 2. Schemas pass check_schema.
    print("\n2. Governance schema self-check")
    for rel in GOVERNANCE_SCHEMAS:
        try:
            Draft202012Validator.check_schema(json.loads(load(rel)))
            print(f"  [{PASS}] {rel}: valid JSON Schema")
        except Exception as exc:
            failures.append(f"{rel}: {exc}")
            print(f"  [{FAIL}] {rel}: {exc}")

    # 3. Enum values present.
    print("\n3. Required enum values")
    for family, (rel, required) in ENUMS.items():
        try:
            enum = enum_of(json.loads(load(rel)), family)
        except Exception as exc:
            failures.append(f"{family}: {exc}")
            print(f"  [{FAIL}] {family}: {exc}")
            continue
        missing = [v for v in required if v not in enum]
        if missing:
            failures.append(f"{family}: missing " + ", ".join(missing))
            print(f"  [{FAIL}] {family}: missing " + ", ".join(missing))
        else:
            print(f"  [{PASS}] {family}: all {len(required)} values present")

    # 4. Transitions + guardrails documented.
    print("\n4. Transitions and agent guardrails")
    trans = load("docs/STATE_TRANSITIONS.md")
    for arrow in REQUIRED_ARROWS:
        if arrow in trans:
            print(f"  [{PASS}] arrow: {arrow}")
        else:
            failures.append(f"missing arrow: {arrow}")
            print(f"  [{FAIL}] missing arrow: {arrow}")
    for g in REQUIRED_GUARDRAILS:
        if g in trans:
            print(f"  [{PASS}] guardrail: '{g}'")
        else:
            failures.append(f"missing guardrail: {g}")
            print(f"  [{FAIL}] missing guardrail: '{g}'")

    # 5. Source-only discipline.
    print("\n5. Source-only discipline")
    if os.path.exists(os.path.join(REPO_ROOT, "examples")):
        failures.append("examples/ exists")
        print(f"  [{FAIL}] examples/ exists")
    else:
        print(f"  [{PASS}] no examples/ directory")
    globs = find_forbidden_globs()
    if globs:
        for g in globs:
            failures.append(f"forbidden artifact: {g}")
            print(f"  [{FAIL}] forbidden artifact: {g}")
    else:
        print(f"  [{PASS}] no *.example.* or redacted artifacts")

    # 6. AgentNet not implemented.
    print("\n6. AgentNet not described as implemented")
    offenders = []
    for root in SCAN_ROOTS:
        p = os.path.join(REPO_ROOT, root)
        files = [p] if os.path.isfile(p) else [
            os.path.join(dp, f) for dp, _, fs in os.walk(p) for f in fs
            if f.endswith((".md", ".py", ".json"))
        ]
        for fp in files:
            if os.path.abspath(fp) in SCAN_SKIP:
                continue
            try:
                norm = re.sub(r"\s+", " ", open(fp, encoding="utf-8").read().lower())
            except (OSError, UnicodeDecodeError):
                continue
            for phrase in AGENTNET_OVERCLAIM:
                start = 0
                while (idx := norm.find(phrase, start)) != -1:
                    start = idx + len(phrase)
                    if not any(n in norm[max(0, idx - 60):idx] for n in AGENTNET_NEGATORS):
                        offenders.append(f"{os.path.relpath(fp, REPO_ROOT)}: '{phrase}'")
    if offenders:
        for o in offenders:
            failures.append(f"AgentNet over-claim: {o}")
            print(f"  [{FAIL}] AgentNet over-claim at {o}")
    else:
        print(f"  [{PASS}] AgentNet described only as intended/not-integrated")

    print("\n" + "=" * 44)
    print("Summary")
    print(f"  failures : {len(failures)}")
    if failures:
        print(f"\nRESULT: {FAIL} ({len(failures)} issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

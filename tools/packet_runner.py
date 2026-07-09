#!/usr/bin/env python3
"""Peak EngagementPacket runner (human-in-the-loop helper).

This is NOT an agent runtime. It makes NO LLM call, NO API call, NO database
query, NO AgentNet lookup, and NO network request. It only reads an
EngagementPacket JSON file locally and prints:

  * a consultant-readable packet summary,
  * the available Phase 3 prompt contracts by workflow,
  * suggested sample-output targets, and
  * next-step instructions for a human consultant.

The consultant does the actual LLM work by hand: open a prompt contract, paste
the packet JSON into its reusable body, review the result, and save it to the
appropriate target file.

Usage:
    python3 tools/packet_runner.py --packet examples/engagement-packet.example.json

Exit status:
  0  -> packet loaded and summarized (structural check passed)
  1  -> packet missing / invalid JSON / failed the structural check
  2  -> bad CLI usage
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")
PACKET_SCHEMA = os.path.join(SCHEMA_DIR, "engagement-packet.schema.json")

# Phase 3 prompt contracts, in first-thread order.
PROMPT_CONTRACTS = [
    ("intake", "prompts/intake/normalize-client-intake.prompt.md"),
    ("discovery", "prompts/discovery/generate-discovery-plan.prompt.md"),
    ("evidence", "prompts/evidence/extract-evidence-findings.prompt.md"),
    ("reporting", "prompts/reporting/draft-initial-assessment-report.prompt.md"),
    ("proposal", "prompts/proposal/generate-next-phase-proposal.prompt.md"),
    ("qa", "prompts/qa/review-assessment-packet.prompt.md"),
    ("learning", "prompts/learning/extract-engagement-lessons.prompt.md"),
]

# Suggested sample-output targets (what a consultant would save reviewed output to).
OUTPUT_TARGETS = [
    ("discovery", "examples/outputs/discovery-plan.alpha.example.md"),
    ("evidence", "examples/outputs/evidence-findings.alpha.example.md"),
    ("reporting", "examples/outputs/initial-assessment-report.alpha.example.md"),
    ("proposal", "examples/outputs/next-phase-proposal.alpha.example.md"),
    ("qa", "examples/outputs/qa-review.alpha.example.md"),
    ("learning", "examples/outputs/engagement-lessons.alpha.example.md"),
]

# Minimum structure a packet must have for this helper to be useful.
REQUIRED_TOP_LEVEL = ["packet_id", "engagement_label", "assessment_stage", "client_intake"]


def load_packet(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def structural_check(packet) -> list[str]:
    """Lightweight, dependency-free structural check.

    If `jsonschema` happens to be installed, additionally validate against the
    EngagementPacket schema with offline $ref resolution (same approach as
    tests/validate_phase2.py). Either way, this never touches the network.
    """
    problems: list[str] = []
    if not isinstance(packet, dict):
        return ["packet is not a JSON object"]
    for key in REQUIRED_TOP_LEVEL:
        if key not in packet:
            problems.append(f"missing required field: {key}")
    intake = packet.get("client_intake")
    if isinstance(intake, dict) and not intake.get("intake_id"):
        problems.append("client_intake.intake_id is missing")

    # Optional stronger check when the dependency is available; skipped silently
    # otherwise so the runner stays usable with the standard library alone.
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        import glob

        resources = []
        for p in glob.glob(os.path.join(SCHEMA_DIR, "*.schema.json")):
            with open(p, "r", encoding="utf-8") as fh:
                schema = json.load(fh)
            if schema.get("$id"):
                resources.append((schema["$id"], Resource.from_contents(schema)))
        registry = Registry().with_resources(resources)
        with open(PACKET_SCHEMA, "r", encoding="utf-8") as fh:
            packet_schema = json.load(fh)
        validator = Draft202012Validator(packet_schema, registry=registry)
        for err in sorted(validator.iter_errors(packet), key=str):
            loc = "/".join(str(x) for x in err.path) or "<root>"
            problems.append(f"schema: at {loc}: {err.message}")
    except ImportError:
        pass  # stdlib-only mode; structural check above is sufficient.

    return problems


def _count(packet, key) -> int:
    val = packet.get(key)
    return len(val) if isinstance(val, list) else 0


def _fmt_list(items) -> str:
    return ", ".join(items) if items else "(none)"


def print_summary(packet) -> None:
    intake = packet.get("client_intake", {}) or {}
    profile = intake.get("client_profile", {}) or {}
    env = intake.get("inventory_environment", {}) or {}
    systems = intake.get("known_systems", []) or []

    print("=" * 66)
    print("PEAK ENGAGEMENT PACKET SUMMARY")
    print("=" * 66)
    print(f"  packet_id            : {packet.get('packet_id', '(unknown)')}")
    print(f"  engagement_label     : {packet.get('engagement_label', '(unknown)')}")
    print(f"  assessment_stage     : {packet.get('assessment_stage', '(unknown)')}")
    print(f"  client organization  : {profile.get('organization_label', '(unknown)')}")
    print(f"  industry             : {intake.get('industry', '(unknown)')}")

    print("\n  Inventory environment:")
    print(f"    product categories : {_fmt_list(env.get('product_categories', []))}")
    print(f"    storage types      : {_fmt_list(env.get('storage_types', []))}")
    print(f"    SKU indicator      : {env.get('sku_count_indicator', '(unknown)')}")
    print(f"    value indicator    : {env.get('inventory_value_indicator', '(unknown)')}")

    print("\n  Known systems:")
    if systems:
        for s in systems:
            name = s.get("name", "(unnamed)")
            cat = s.get("category", "?")
            print(f"    - {name} [{cat}]")
    else:
        print("    (none)")

    print("\n  Discovery contents:")
    print(f"    evidence records         : {_count(packet, 'evidence_references')}")
    print(f"    stakeholder interviews   : {_count(packet, 'stakeholder_interviews')}")
    print(f"    visual observations      : {_count(packet, 'visual_observations')}")
    print(f"    workflow observations    : {_count(packet, 'workflow_observations')}")


def print_contracts() -> None:
    print("\n" + "=" * 66)
    print("AVAILABLE PROMPT CONTRACTS (Phase 3, by workflow)")
    print("=" * 66)
    for workflow, path in PROMPT_CONTRACTS:
        exists = "" if os.path.isfile(os.path.join(REPO_ROOT, path)) else "  [MISSING]"
        print(f"  {workflow:<10} {path}{exists}")


def print_targets() -> None:
    print("\n" + "=" * 66)
    print("SUGGESTED SAMPLE-OUTPUT TARGETS")
    print("=" * 66)
    for workflow, path in OUTPUT_TARGETS:
        print(f"  {workflow:<10} {path}")


def print_next_steps(packet_path: str) -> None:
    rel = os.path.relpath(packet_path, REPO_ROOT)
    print("\n" + "=" * 66)
    print("NEXT STEPS (human-in-the-loop)")
    print("=" * 66)
    print("  For each workflow you want to run:")
    print("    1. Open the relevant prompt contract listed above.")
    print("    2. Copy its 'Reusable prompt body' block into your chosen LLM.")
    print(f"    3. Paste this packet's JSON ({rel}) where the prompt says to.")
    print("    4. Review and edit the output yourself — you own it.")
    print("    5. Save the reviewed result to the matching sample-output target.")

    print("\n" + "-" * 66)
    print("  This runner did NOT do any of the following:")
    print("    * No LLM call was made.")
    print("    * No AgentNet lookup was made (AgentNet is intended future")
    print("      grounding architecture, not integrated).")
    print("    * No client-facing output was generated automatically.")
    print("    * No API, database, or network request was made.")
    print("-" * 66)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize an EngagementPacket and point a consultant to the "
        "right prompt contracts. Read-only; makes no LLM/API/network call."
    )
    parser.add_argument(
        "--packet",
        required=True,
        help="Path to an EngagementPacket JSON file.",
    )
    args = parser.parse_args(argv)

    packet_path = args.packet
    if not os.path.isfile(packet_path):
        print(f"ERROR: packet file not found: {packet_path}", file=sys.stderr)
        return 1

    try:
        packet = load_packet(packet_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read packet JSON: {exc}", file=sys.stderr)
        return 1

    problems = structural_check(packet)
    if problems:
        print("ERROR: packet failed structural check:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print_summary(packet)
    print_contracts()
    print_targets()
    print_next_steps(packet_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

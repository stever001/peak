#!/usr/bin/env python3
"""Peak EngagementPacket runner (human-in-the-loop helper).

This is NOT an agent runtime. It makes NO LLM call, NO API call, NO database
query, NO AgentNet lookup, and NO network request. It reads an EngagementPacket JSON
file provided with --packet and prints:

  * a consultant-readable packet summary,
  * the available prompt contracts by workflow, and
  * next-step instructions for a human consultant.

The runner does not store, write, or commit any packet, and it does not generate demo
or sample packets. Provide a real packet from controlled engagement storage (an
authorized engagement workspace) or, in tests only, a temporary fixture file. Real
engagement packets live in controlled engagement storage, not in this repository (see
docs/DATA_HANDLING_POLICY.md and docs/FIXTURE_STRATEGY.md).

Usage:
    python3 tools/packet_runner.py --packet /path/to/engagement-packet.json

Exit status:
  0  -> packet loaded/summarized (structural check passed)
  1  -> packet missing / invalid JSON / failed the structural check
  2  -> bad CLI usage
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Prompt contracts, in first-thread order.
PROMPT_CONTRACTS = [
    ("intake", "prompts/intake/normalize-client-intake.prompt.md"),
    ("discovery", "prompts/discovery/generate-discovery-plan.prompt.md"),
    ("evidence", "prompts/evidence/extract-evidence-findings.prompt.md"),
    ("reporting", "prompts/reporting/draft-initial-assessment-report.prompt.md"),
    ("proposal", "prompts/proposal/generate-next-phase-proposal.prompt.md"),
    ("qa", "prompts/qa/review-assessment-packet.prompt.md"),
    ("learning", "prompts/learning/extract-engagement-lessons.prompt.md"),
]

REQUIRED_TOP_LEVEL = ["packet_id", "engagement_label", "assessment_stage", "client_intake"]


def load_packet(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def structural_check(packet) -> list[str]:
    problems: list[str] = []
    if not isinstance(packet, dict):
        return ["packet is not a JSON object"]
    for key in REQUIRED_TOP_LEVEL:
        if key not in packet:
            problems.append(f"missing required field: {key}")
    intake = packet.get("client_intake")
    if isinstance(intake, dict) and not intake.get("intake_id"):
        problems.append("client_intake.intake_id is missing")
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
            print(f"    - {s.get('name', '(unnamed)')} [{s.get('category', '?')}]")
    else:
        print("    (none)")

    print("\n  Discovery contents:")
    print(f"    evidence records         : {_count(packet, 'evidence_references')}")
    print(f"    stakeholder interviews   : {_count(packet, 'stakeholder_interviews')}")
    print(f"    visual observations      : {_count(packet, 'visual_observations')}")
    print(f"    workflow observations    : {_count(packet, 'workflow_observations')}")


def print_contracts() -> None:
    print("\n" + "=" * 66)
    print("AVAILABLE PROMPT CONTRACTS (by workflow)")
    print("=" * 66)
    for workflow, path in PROMPT_CONTRACTS:
        exists = "" if os.path.isfile(os.path.join(REPO_ROOT, path)) else "  [MISSING]"
        print(f"  {workflow:<10} {path}{exists}")


def print_next_steps(source_label: str) -> None:
    print("\n" + "=" * 66)
    print("NEXT STEPS (human-in-the-loop)")
    print("=" * 66)
    print("  For each workflow you want to run:")
    print("    1. Open the relevant prompt contract listed above.")
    print("    2. Copy its 'Reusable prompt body' block into your chosen LLM.")
    print(f"    3. Paste this packet's JSON ({source_label}) where the prompt says to.")
    print("    4. Review and edit the output yourself — you own it.")
    print("    5. Save reviewed output to controlled engagement storage — NOT this repo.")

    print("\n" + "-" * 66)
    print("  This runner did NOT do any of the following:")
    print("    * No LLM call was made.")
    print("    * No AgentNet lookup was made (AgentNet is intended future")
    print("      grounding architecture, not integrated).")
    print("    * No client-facing output was generated automatically.")
    print("    * No API, database, or network request was made.")
    print("    * No packet was written, stored, or committed to the repo.")
    print("-" * 66)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize an EngagementPacket and point a consultant to the right "
        "prompt contracts. Read-only; makes no LLM/API/network call; stores nothing."
    )
    parser.add_argument(
        "--packet",
        required=True,
        help="Path to an EngagementPacket JSON file from controlled engagement storage "
        "(or a temporary test fixture).",
    )
    args = parser.parse_args(argv)

    if not os.path.isfile(args.packet):
        print(f"ERROR: packet file not found: {args.packet}", file=sys.stderr)
        return 1
    try:
        packet = load_packet(args.packet)
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
    print_next_steps(args.packet)
    return 0


if __name__ == "__main__":
    sys.exit(main())

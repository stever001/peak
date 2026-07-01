#!/usr/bin/env python3
"""Phase 2 validation harness: the EngagementPacket.

The EngagementPacket composes the Phase 1 object schemas via local relative
`$ref`. This harness resolves those refs OFFLINE (no network) by building a
`referencing` registry from the sibling schema files, then runs:

  1. Schema self-check     - every schemas/*.schema.json is valid draft 2020-12,
                             including engagement-packet.schema.json.
  2. Packet conformance    - examples/engagement-packet.example.json validates
                             against the packet schema with refs resolved.
  3. Packet referential lint (BLOCKING) - inside the packet:
       * every `evidence_references` id (nested anywhere) resolves to an
         EvidenceReference declared in the packet's top-level
         evidence_references[] by evidence_id;
       * inventory_system_profile.related_intake_id, and the related_intake_id
         of every interview / visual / workflow observation, equals the
         packet's client_intake.intake_id;
       * ids use their expected prefixes.

Unlike the Phase 1 standalone lint (where cross-packet references are non-blocking
warnings), packet-level unresolved references are FAILURES: a packet is meant to be
self-contained.

Exit status:
  0  -> all blocking checks passed
  1  -> a schema, conformance, or packet-referential check failed
  2  -> a dependency is missing (install requirements-dev.txt)
"""

from __future__ import annotations

import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")
EXAMPLE_DIR = os.path.join(REPO_ROOT, "examples")

PACKET_SCHEMA = os.path.join(SCHEMA_DIR, "engagement-packet.schema.json")
PACKET_EXAMPLE = os.path.join(EXAMPLE_DIR, "engagement-packet.example.json")

KNOWN_PREFIXES = {
    "intake_": "ClientIntake",
    "evid_": "EvidenceReference",
    "intv_": "StakeholderInterview",
    "vobs_": "VisualObservation",
    "wobs_": "WorkflowObservation",
    "isp_": "InventorySystemProfile",
    "pkt_": "EngagementPacket",
}

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.checks_run = 0

    def ok(self, msg: str) -> None:
        self.checks_run += 1
        print(f"  [{PASS}] {msg}")

    def fail(self, msg: str) -> None:
        self.checks_run += 1
        self.failures.append(msg)
        print(f"  [{FAIL}] {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  [{WARN}] {msg}")

    def section(self, title: str) -> None:
        print(f"\n{title}")


def load_json(path: str) -> object:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_registry(schemas: dict[str, dict]):
    """Build an offline referencing registry keyed by each schema's $id.

    The packet's relative $refs (e.g. 'client-intake.schema.json') resolve
    against the packet $id base, which yields the sibling schema's $id -- so
    keying by $id is sufficient and requires no network access.
    """
    from referencing import Registry, Resource

    resources = []
    for schema in schemas.values():
        sid = schema.get("$id")
        if sid:
            resources.append((sid, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def walk(node, path=""):
    """Yield (json_path, key, value) for every key/value in a nested document."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}/{key}"
            yield here, key, value
            yield from walk(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk(item, f"{path}/{i}")


def as_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def check_schemas(reporter: Reporter, validator_cls) -> dict[str, dict]:
    reporter.section("1. Schema self-check (draft 2020-12)")
    schemas: dict[str, dict] = {}
    for path in sorted(glob.glob(os.path.join(SCHEMA_DIR, "*.schema.json"))):
        name = os.path.basename(path)
        try:
            schema = load_json(path)
            validator_cls.check_schema(schema)
        except Exception as exc:
            reporter.fail(f"{name}: {exc}")
            continue
        schemas[path] = schema
        reporter.ok(f"{name}: valid JSON Schema")
    return schemas


def check_packet_conformance(reporter, schemas, validator_cls, registry):
    reporter.section("2. Packet conformance (with local $ref resolution)")
    if PACKET_SCHEMA not in schemas:
        reporter.fail("engagement-packet.schema.json not found")
        return None
    try:
        packet = load_json(PACKET_EXAMPLE)
    except (OSError, json.JSONDecodeError) as exc:
        reporter.fail(f"engagement-packet.example.json: {exc}")
        return None

    validator = validator_cls(schemas[PACKET_SCHEMA], registry=registry)
    errors = sorted(validator.iter_errors(packet), key=str)
    if errors:
        for err in errors:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            reporter.fail(f"engagement-packet.example.json: at {loc}: {err.message}")
        return None
    reporter.ok("engagement-packet.example.json: conforms to engagement-packet.schema.json")
    return packet


def check_packet_references(reporter: Reporter, packet: dict) -> None:
    reporter.section("3. Packet referential lint (blocking)")

    # Anchor intake id.
    intake = packet.get("client_intake", {})
    anchor = intake.get("intake_id")
    if not isinstance(anchor, str):
        reporter.fail("client_intake.intake_id is missing")
        return
    if not anchor.startswith("intake_"):
        reporter.fail(f"client_intake.intake_id '{anchor}' should start with 'intake_'")

    # packet_id prefix.
    pkt_id = packet.get("packet_id")
    if isinstance(pkt_id, str) and not pkt_id.startswith("pkt_"):
        reporter.fail(f"packet_id '{pkt_id}' should start with 'pkt_'")

    # Declared evidence ids (the packet's evidence store).
    declared_evidence = {
        e.get("evidence_id")
        for e in packet.get("evidence_references", [])
        if isinstance(e, dict) and isinstance(e.get("evidence_id"), str)
    }

    # 3a. Every nested evidence_references id resolves within the packet.
    unresolved = 0
    bad_prefix = 0
    for jpath, key, value in walk(packet):
        if key != "evidence_references":
            continue
        # Skip the top-level declaration list of EvidenceReference OBJECTS;
        # we only lint the string-id usages.
        for ref in as_strings(value):
            if not ref.startswith("evid_"):
                bad_prefix += 1
                reporter.fail(f"{jpath}: evidence id '{ref}' should start with 'evid_'")
            elif ref not in declared_evidence:
                unresolved += 1
                reporter.fail(
                    f"{jpath}: evidence_references '{ref}' does not resolve to any "
                    f"EvidenceReference in the packet"
                )
    if unresolved == 0 and bad_prefix == 0:
        reporter.ok(
            f"all nested evidence_references resolve within the packet "
            f"({len(declared_evidence)} evidence records declared)"
        )

    # 3b. related_intake_id everywhere matches the anchor.
    mismatches = 0

    def check_related(obj, label):
        nonlocal mismatches
        if not isinstance(obj, dict):
            return
        rid = obj.get("related_intake_id")
        if rid is None:
            return
        if rid != anchor:
            mismatches += 1
            reporter.fail(
                f"{label}: related_intake_id '{rid}' does not match "
                f"client_intake.intake_id '{anchor}'"
            )

    check_related(packet.get("inventory_system_profile"), "inventory_system_profile")
    for i, itv in enumerate(packet.get("stakeholder_interviews", [])):
        check_related(itv, f"stakeholder_interviews/{i}")
    for i, obs in enumerate(packet.get("visual_observations", [])):
        check_related(obs, f"visual_observations/{i}")
    for i, obs in enumerate(packet.get("workflow_observations", [])):
        check_related(obs, f"workflow_observations/{i}")
    if mismatches == 0:
        reporter.ok(f"all nested related_intake_id values match '{anchor}'")

    # 3c. related_object_ids use known prefixes (advisory prefix check).
    unknown = 0
    for jpath, key, value in walk(packet):
        if key != "related_object_ids":
            continue
        for ref in as_strings(value):
            if not any(ref.startswith(p) for p in KNOWN_PREFIXES):
                unknown += 1
                reporter.fail(f"{jpath}: related_object_ids '{ref}' has no known prefix")
    if unknown == 0:
        reporter.ok("all related_object_ids use known prefixes")


def main() -> int:
    print("Peak Phase 2 validation harness (EngagementPacket)")
    print("=" * 50)

    try:
        from jsonschema import Draft202012Validator as validator_cls
    except ImportError:
        print(
            "\nERROR: the 'jsonschema' package is required.\n"
            "Install dev dependencies:\n"
            "    make install-dev\n"
            "    (or: python3 -m pip install -r requirements-dev.txt)\n",
            file=sys.stderr,
        )
        return 2

    reporter = Reporter()
    schemas = check_schemas(reporter, validator_cls)
    registry = build_registry(schemas)
    packet = check_packet_conformance(reporter, schemas, validator_cls, registry)
    if packet is not None:
        check_packet_references(reporter, packet)

    print("\n" + "=" * 50)
    print("Summary")
    print(f"  checks run : {reporter.checks_run}")
    print(f"  failures   : {len(reporter.failures)}")
    print(f"  warnings   : {len(reporter.warnings)}")

    if reporter.failures:
        print(f"\nRESULT: {FAIL} ({len(reporter.failures)} blocking issue(s))")
        return 1
    if reporter.warnings:
        print(f"\nRESULT: {PASS} (with {len(reporter.warnings)} non-blocking warning(s))")
        return 0
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

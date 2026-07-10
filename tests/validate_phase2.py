#!/usr/bin/env python3
"""Phase 2 validation harness: the EngagementPacket (synthetic fixture).

The EngagementPacket composes the object schemas via local relative `$ref`. This
harness resolves those refs OFFLINE by building a `referencing` registry from the
sibling schema files, then validates a **synthetic, generated** packet — no committed
example data.

  1. Schema self-check      - every schemas/*.schema.json is valid draft 2020-12.
  2. Packet conformance     - a synthetic EngagementPacket (built in memory by
                              tests/synthetic_fixtures.py, written to a TEMPORARY
                              directory, then discarded) validates against
                              engagement-packet.schema.json with refs resolved.
  3. Packet referential lint (BLOCKING) - inside the synthetic packet:
       * every nested `evidence_references` id resolves to a declared
         EvidenceReference;
       * every nested `related_intake_id` equals client_intake.intake_id;
       * ids use their expected prefixes.

No stored packet artifact is read or required. See docs/FIXTURE_STRATEGY.md.

Exit status:
  0  -> all blocking checks passed
  1  -> a schema, conformance, or packet-referential check failed
  2  -> a dependency is missing
"""

from __future__ import annotations

import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import synthetic_fixtures as sf  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")
PACKET_SCHEMA = os.path.join(SCHEMA_DIR, "engagement-packet.schema.json")

KNOWN_PREFIXES = ("intake_", "evid_", "intv_", "vobs_", "wobs_", "isp_", "pkt_")

PASS = "PASS"
FAIL = "FAIL"


class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checks_run = 0

    def ok(self, msg: str) -> None:
        self.checks_run += 1
        print(f"  [{PASS}] {msg}")

    def fail(self, msg: str) -> None:
        self.checks_run += 1
        self.failures.append(msg)
        print(f"  [{FAIL}] {msg}")

    def section(self, title: str) -> None:
        print(f"\n{title}")


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_registry(schemas):
    from referencing import Registry, Resource

    resources = []
    for schema in schemas.values():
        sid = schema.get("$id")
        if sid:
            resources.append((sid, Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}/{key}"
            yield here, key, value
            yield from walk(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from walk(item, f"{path}/{i}")


def as_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def check_schemas(reporter, validator_cls):
    reporter.section("1. Schema self-check (draft 2020-12)")
    schemas = {}
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
    reporter.section("2. Synthetic packet conformance (offline $ref resolution)")
    if PACKET_SCHEMA not in schemas:
        reporter.fail("engagement-packet.schema.json not found")
        return None
    with tempfile.TemporaryDirectory(prefix="peak-synthetic-") as tmp:
        packet = sf.synthetic_engagement_packet()
        fpath = os.path.join(tmp, "engagement-packet.synthetic.json")
        with open(fpath, "w", encoding="utf-8") as fh:
            json.dump(packet, fh)
        packet = load_json(fpath)
        validator = validator_cls(schemas[PACKET_SCHEMA], registry=registry)
        errors = sorted(validator.iter_errors(packet), key=str)
    if errors:
        for err in errors:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            reporter.fail(f"synthetic packet: at {loc}: {err.message}")
        return None
    reporter.ok("synthetic packet conforms to engagement-packet.schema.json")
    return packet


def check_packet_references(reporter, packet):
    reporter.section("3. Packet referential lint (blocking)")

    intake = packet.get("client_intake", {})
    anchor = intake.get("intake_id")
    if not isinstance(anchor, str):
        reporter.fail("client_intake.intake_id is missing")
        return
    if not anchor.startswith("intake_"):
        reporter.fail(f"client_intake.intake_id '{anchor}' should start with 'intake_'")

    pkt_id = packet.get("packet_id")
    if isinstance(pkt_id, str) and not pkt_id.startswith("pkt_"):
        reporter.fail(f"packet_id '{pkt_id}' should start with 'pkt_'")

    declared_evidence = {
        e.get("evidence_id")
        for e in packet.get("evidence_references", [])
        if isinstance(e, dict) and isinstance(e.get("evidence_id"), str)
    }

    unresolved = 0
    bad_prefix = 0
    for jpath, key, value in walk(packet):
        if key != "evidence_references":
            continue
        for ref in as_strings(value):
            if not ref.startswith("evid_"):
                bad_prefix += 1
                reporter.fail(f"{jpath}: evidence id '{ref}' should start with 'evid_'")
            elif ref not in declared_evidence:
                unresolved += 1
                reporter.fail(f"{jpath}: evidence_references '{ref}' does not resolve in the packet")
    if unresolved == 0 and bad_prefix == 0:
        reporter.ok(f"all nested evidence_references resolve within the packet ({len(declared_evidence)} declared)")

    mismatches = 0

    def check_related(obj, label):
        nonlocal mismatches
        if isinstance(obj, dict):
            rid = obj.get("related_intake_id")
            if rid is not None and rid != anchor:
                mismatches += 1
                reporter.fail(f"{label}: related_intake_id '{rid}' does not match '{anchor}'")

    check_related(packet.get("inventory_system_profile"), "inventory_system_profile")
    for i, itv in enumerate(packet.get("stakeholder_interviews", [])):
        check_related(itv, f"stakeholder_interviews/{i}")
    for i, obs in enumerate(packet.get("visual_observations", [])):
        check_related(obs, f"visual_observations/{i}")
    for i, obs in enumerate(packet.get("workflow_observations", [])):
        check_related(obs, f"workflow_observations/{i}")
    if mismatches == 0:
        reporter.ok(f"all nested related_intake_id values match '{anchor}'")

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
    print("Peak Phase 2 validation harness (synthetic EngagementPacket)")
    print("=" * 60)

    try:
        from jsonschema import Draft202012Validator as validator_cls
    except ImportError:
        print(
            "\nERROR: the 'jsonschema' package is required.\n"
            "    make install-dev\n",
            file=sys.stderr,
        )
        return 2

    reporter = Reporter()
    schemas = check_schemas(reporter, validator_cls)
    registry = build_registry(schemas)
    packet = check_packet_conformance(reporter, schemas, validator_cls, registry)
    if packet is not None:
        check_packet_references(reporter, packet)

    print("\n" + "=" * 60)
    print("Summary")
    print(f"  checks run : {reporter.checks_run}")
    print(f"  failures   : {len(reporter.failures)}")
    if reporter.failures:
        print(f"\nRESULT: {FAIL} ({len(reporter.failures)} blocking issue(s))")
        return 1
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

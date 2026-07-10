#!/usr/bin/env python3
"""Phase 1 validation harness for Peak's internal AI operating system.

Runs over the standalone object schemas using **synthetic, generated fixtures** — no
committed example data:

  1. Schema self-check     - every schemas/*.schema.json is a valid JSON Schema
                             (draft 2020-12).
  2. Fixture conformance   - a synthetic instance of each object (built in memory by
                             tests/synthetic_fixtures.py, written to a TEMPORARY
                             directory, then discarded) validates against its schema.
  3. Prefix lint           - synthetic ids and references use their expected prefixes.

No stored example artifacts are read or required. The temporary fixture files are
created with tempfile and auto-deleted; nothing is committed. See
docs/FIXTURE_STRATEGY.md.

Exit status:
  0  -> all blocking checks passed
  1  -> a schema or fixture validation check failed
  2  -> a dependency is missing (e.g. jsonschema not installed)
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

KNOWN_PREFIXES = ("intake_", "evid_", "intv_", "vobs_", "wobs_", "isp_", "pkt_")

ID_FIELDS = {
    "intake_id": "intake_",
    "evidence_id": "evid_",
    "interview_id": "intv_",
    "system_profile_id": "isp_",
}
REFERENCE_FIELDS = {
    "related_intake_id": "intake_",
    "evidence_references": "evid_",
    "related_object_ids": None,
}

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


def iter_reference_strings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in REFERENCE_FIELDS:
                items = [value] if isinstance(value, str) else value
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, str):
                            yield key, item
            else:
                yield from iter_reference_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_reference_strings(item)


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
        schemas[name] = schema
        reporter.ok(f"{name}: valid JSON Schema")
    return schemas


def check_fixtures(reporter, schemas, validator_cls):
    reporter.section("2. Synthetic fixture conformance (generated in a temp dir)")
    fixtures = {}
    with tempfile.TemporaryDirectory(prefix="peak-synthetic-") as tmp:
        for stem, builder in sf.STANDALONE_BUILDERS.items():
            schema_name = f"{stem}.schema.json"
            if schema_name not in schemas:
                reporter.fail(f"{stem}: no matching schema ({schema_name})")
                continue
            fixture = builder()
            # Write to a temporary file (auto-deleted) to exercise the on-disk path
            # without committing anything.
            fpath = os.path.join(tmp, f"{stem}.synthetic.json")
            with open(fpath, "w", encoding="utf-8") as fh:
                json.dump(fixture, fh)
            doc = load_json(fpath)
            fixtures[stem] = doc
            errors = sorted(validator_cls(schemas[schema_name]).iter_errors(doc), key=str)
            if errors:
                for err in errors:
                    loc = "/".join(str(p) for p in err.path) or "<root>"
                    reporter.fail(f"{stem}: at {loc}: {err.message}")
            else:
                reporter.ok(f"{stem}: synthetic fixture conforms to {schema_name}")
    return fixtures


def check_prefixes(reporter, fixtures):
    reporter.section("3. Prefix lint (synthetic fixtures)")
    problems = 0
    for stem, doc in sorted(fixtures.items()):
        for field, prefix in ID_FIELDS.items():
            val = doc.get(field)
            if isinstance(val, str) and not val.startswith(prefix):
                problems += 1
                reporter.fail(f"{stem}: {field} '{val}' should start with '{prefix}'")
        for field, ref in iter_reference_strings(doc):
            required = REFERENCE_FIELDS[field]
            if required is None:
                if not any(ref.startswith(p) for p in KNOWN_PREFIXES):
                    problems += 1
                    reporter.fail(f"{stem}: {field} '{ref}' has no known prefix")
            elif not ref.startswith(required):
                problems += 1
                reporter.fail(f"{stem}: {field} '{ref}' should start with '{required}'")
    if problems == 0:
        reporter.ok("all synthetic ids and references use known prefixes")


def main() -> int:
    print("Peak Phase 1 validation harness (synthetic fixtures)")
    print("=" * 51)

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
    fixtures = check_fixtures(reporter, schemas, validator_cls)
    check_prefixes(reporter, fixtures)

    print("\n" + "=" * 51)
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

#!/usr/bin/env python3
"""Phase 1 validation harness for Peak's internal AI operating system.

Runs three checks over the first-thread assessment schemas and examples:

  1. Schema self-check   - every schemas/*.schema.json is a valid JSON Schema
                           (draft 2020-12).
  2. Example conformance - every examples/*.example.json validates against its
                           matching schema (by filename convention).
  3. Referential lint    - local ids and cross-references use their expected
                           prefixes; unresolved references are reported as
                           WARNINGS, not failures (for now).

Exit status:
  0  -> all blocking checks passed (warnings allowed)
  1  -> a schema or example validation check failed
  2  -> a dependency is missing (e.g. jsonschema not installed)

This harness is deliberately dependency-light: standard library plus
`jsonschema` (see requirements-dev.txt). No pytest, database, or network.
"""

from __future__ import annotations

import glob
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_DIR = os.path.join(REPO_ROOT, "schemas")
EXAMPLE_DIR = os.path.join(REPO_ROOT, "examples")

# Known local-id prefixes and the object each denotes.
KNOWN_PREFIXES = {
    "intake_": "ClientIntake",
    "evid_": "EvidenceReference",
    "intv_": "StakeholderInterview",
    "vobs_": "VisualObservation",
    "wobs_": "WorkflowObservation",
    "isp_": "InventorySystemProfile",
}

# Fields whose values are cross-references, and the prefix rule for each.
#   None  -> value(s) may use ANY known prefix
#   str   -> value(s) must use this specific prefix
REFERENCE_FIELDS = {
    "related_intake_id": "intake_",
    "evidence_references": "evid_",
    "related_object_ids": None,
}

# Fields that hold an object's own local id, matched to their required prefix.
ID_FIELDS = {
    "intake_id": "intake_",
    "evidence_id": "evid_",
    "interview_id": "intv_",
    "system_profile_id": "isp_",
    # VisualObservation and WorkflowObservation both use `observation_id`;
    # the acceptable prefix depends on the source file, handled separately.
}

# ANSI-free status tokens keep output portable across terminals and logs.
PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


class Reporter:
    """Collects results and prints a readable, portable summary."""

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


def schema_name_for_example(example_path: str) -> str:
    """`examples/foo.example.json` -> `schemas/foo.schema.json`."""
    base = os.path.basename(example_path)
    stem = base[: -len(".example.json")]
    return os.path.join(SCHEMA_DIR, f"{stem}.schema.json")


def iter_reference_strings(node: object):
    """Yield (field_name, value) for every reference-field string in a document.

    Walks nested dicts and lists so references buried inside arrays of objects
    (e.g. a pain point's evidence_references) are inspected too.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key in REFERENCE_FIELDS:
                for item in _as_strings(value):
                    yield key, item
            else:
                yield from iter_reference_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from iter_reference_strings(item)


def _as_strings(value: object):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def collect_declared_ids(examples: dict[str, object]) -> set[str]:
    """Gather every declared local id across all example documents."""
    declared: set[str] = set()
    for doc in examples.values():
        if not isinstance(doc, dict):
            continue
        for field in list(ID_FIELDS) + ["observation_id"]:
            val = doc.get(field)
            if isinstance(val, str):
                declared.add(val)
    return declared


def has_known_prefix(value: str) -> bool:
    return any(value.startswith(p) for p in KNOWN_PREFIXES)


def check_schemas(reporter: Reporter, validator_cls) -> dict[str, object]:
    reporter.section("1. Schema self-check (draft 2020-12)")
    schemas: dict[str, object] = {}
    paths = sorted(glob.glob(os.path.join(SCHEMA_DIR, "*.schema.json")))
    if not paths:
        reporter.fail("no schema files found in schemas/")
        return schemas
    for path in paths:
        name = os.path.basename(path)
        try:
            schema = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            reporter.fail(f"{name}: could not parse JSON ({exc})")
            continue
        try:
            validator_cls.check_schema(schema)
        except Exception as exc:  # jsonschema.exceptions.SchemaError
            reporter.fail(f"{name}: invalid schema ({exc})")
            continue
        schemas[path] = schema
        reporter.ok(f"{name}: valid JSON Schema")
    return schemas


def check_examples(
    reporter: Reporter, schemas: dict[str, object], validator_cls
) -> dict[str, object]:
    reporter.section("2. Example conformance")
    examples: dict[str, object] = {}
    paths = sorted(glob.glob(os.path.join(EXAMPLE_DIR, "*.example.json")))
    if not paths:
        reporter.fail("no example files found in examples/")
        return examples
    for path in paths:
        name = os.path.basename(path)
        try:
            doc = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            reporter.fail(f"{name}: could not parse JSON ({exc})")
            continue
        examples[path] = doc

        schema_path = schema_name_for_example(path)
        if schema_path not in schemas:
            reporter.fail(
                f"{name}: no matching schema ({os.path.basename(schema_path)})"
            )
            continue

        errors = sorted(
            validator_cls(schemas[schema_path]).iter_errors(doc), key=str
        )
        if errors:
            for err in errors:
                loc = "/".join(str(p) for p in err.path) or "<root>"
                reporter.fail(f"{name}: at {loc}: {err.message}")
        else:
            reporter.ok(f"{name}: conforms to {os.path.basename(schema_path)}")
    return examples


def check_references(reporter: Reporter, examples: dict[str, object]) -> None:
    reporter.section("3. Referential lint")
    if not examples:
        reporter.warn("no examples to lint")
        return

    declared_ids = collect_declared_ids(examples)
    prefix_problems = 0
    unresolved = 0

    for path in sorted(examples):
        name = os.path.basename(path)
        doc = examples[path]
        if not isinstance(doc, dict):
            continue

        # 3a. Own-id prefix checks.
        for field, prefix in ID_FIELDS.items():
            val = doc.get(field)
            if isinstance(val, str) and not val.startswith(prefix):
                prefix_problems += 1
                reporter.fail(
                    f"{name}: {field} '{val}' should start with '{prefix}'"
                )

        # `observation_id` is shared by visual/workflow observations.
        obs_id = doc.get("observation_id")
        if isinstance(obs_id, str):
            expected = "vobs_" if "visual" in name else (
                "wobs_" if "workflow" in name else None
            )
            if expected and not obs_id.startswith(expected):
                prefix_problems += 1
                reporter.fail(
                    f"{name}: observation_id '{obs_id}' should start with "
                    f"'{expected}'"
                )
            elif expected is None and not has_known_prefix(obs_id):
                prefix_problems += 1
                reporter.fail(
                    f"{name}: observation_id '{obs_id}' has no known prefix"
                )

        # 3b. Cross-reference prefix checks (recursive).
        for field, prefix in iter_reference_strings(doc):
            required = REFERENCE_FIELDS[field]
            if required is None:
                if not has_known_prefix(prefix):
                    prefix_problems += 1
                    reporter.fail(
                        f"{name}: {field} value '{prefix}' has no known prefix"
                    )
            elif not prefix.startswith(required):
                prefix_problems += 1
                reporter.fail(
                    f"{name}: {field} value '{prefix}' should start with "
                    f"'{required}'"
                )

    # 3c. Unresolved references -> WARNINGS only, for now.
    for path in sorted(examples):
        name = os.path.basename(path)
        doc = examples[path]
        if not isinstance(doc, dict):
            continue
        for field, ref in iter_reference_strings(doc):
            if not has_known_prefix(ref):
                continue  # already reported as a prefix problem above
            if ref not in declared_ids:
                unresolved += 1
                reporter.warn(
                    f"{name}: {field} '{ref}' not resolved in the example set "
                    f"(ok for now)"
                )

    if prefix_problems == 0:
        reporter.ok(
            f"all ids and references use known prefixes "
            f"({len(declared_ids)} ids declared)"
        )
    if unresolved:
        print(
            f"\n  note: {unresolved} reference(s) point outside the example set. "
            f"This is allowed in Phase 1 because not every referenced object has "
            f"an example file yet."
        )


def main() -> int:
    print("Peak Phase 1 validation harness")
    print("=" * 40)

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
    examples = check_examples(reporter, schemas, validator_cls)
    check_references(reporter, examples)

    # Summary.
    print("\n" + "=" * 40)
    print("Summary")
    print(f"  checks run : {reporter.checks_run}")
    print(f"  failures   : {len(reporter.failures)}")
    print(f"  warnings   : {len(reporter.warnings)}")

    if reporter.failures:
        print(f"\nRESULT: {FAIL} ({len(reporter.failures)} blocking issue(s))")
        return 1
    if reporter.warnings:
        print(
            f"\nRESULT: {PASS} (with {len(reporter.warnings)} non-blocking "
            f"warning(s))"
        )
        return 0
    print(f"\nRESULT: {PASS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

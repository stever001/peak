# Tests

Validation for the Phase 1 assessment schemas and examples. Deliberately
dependency-light: Python standard library plus `jsonschema`. No pytest, no
database, no API server, no network.

## `validate_phase1.py`

Runs three checks over [`../schemas/`](../schemas/) and [`../examples/`](../examples/):

1. **Schema self-check** — every `schemas/*.schema.json` is a valid JSON Schema
   under draft 2020-12 (`check_schema`).
2. **Example conformance** — every `examples/*.example.json` validates against its
   matching schema, paired by filename convention
   (`foo.example.json` → `foo.schema.json`).
3. **Referential lint** — local ids and cross-references use their expected
   prefixes (`intake_`, `evid_`, `intv_`, `vobs_`, `wobs_`, `isp_`).
   `related_intake_id` must use `intake_`, `evidence_references` must use `evid_`,
   and `related_object_ids` must use one of the known prefixes. References are
   matched recursively, including those nested inside arrays of objects.

### Unresolved references are warnings, not failures

If a reference points at an id that has no example object in the set (e.g.
`evid_alpha_003`, which no `*.example.json` declares yet), it is reported as a
**warning**. This is intentional for Phase 1: not every referenced object has an
example file. Referential *integrity* (every reference resolves) can be promoted to
a blocking check in a later phase once full engagement packets exist.

## Running

```bash
# one-time: install the dev dependency
python -m pip install -r ../requirements-dev.txt

# from the repo root
python tests/validate_phase1.py
```

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. Warnings may be present. |
| `1` | A schema or example validation check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure / zero-on-warnings-only behavior makes this harness safe to
wire into CI later without additional tooling.

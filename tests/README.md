# Tests

Validation for the assessment schemas and examples. Deliberately dependency-light:
Python standard library plus `jsonschema` (which brings `referencing`). No pytest,
no database, no API server, no network.

Two harnesses, run together by `make validate`:

- `validate_phase1.py` — the six standalone Phase 1 objects.
- `validate_phase2.py` — the composite `EngagementPacket`.

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
`evid_alpha_003`, which no standalone `*.example.json` declares), it is reported as a
**warning**. This is intentional for the standalone objects: they are single records,
not a packaged engagement. The composite `EngagementPacket` is where these references
are expected to resolve — and there they are checked strictly (below).

The composite `engagement-packet.example.json` is **skipped** by this harness (shown
as `[SKIP]`) because it composes other schemas via `$ref` and needs offline ref
resolution plus packet-level linting — that is `validate_phase2.py`'s job.

## `validate_phase2.py`

Validates the `EngagementPacket`, which composes the Phase 1 schemas via local
relative `$ref`. Refs are resolved **offline**: the harness builds a `referencing`
registry from every schema's `$id`, so no network or database is touched.

1. **Schema self-check** — all schemas, including `engagement-packet.schema.json`.
2. **Packet conformance** — `engagement-packet.example.json` validates against the
   packet schema with `$ref`s resolved.
3. **Packet referential lint (blocking)** — unlike the Phase 1 standalone lint,
   these are **failures**, because a packet is meant to be self-contained:
   - every nested `evidence_references` id resolves to an `EvidenceReference`
     declared in the packet's `evidence_references[]`;
   - `inventory_system_profile.related_intake_id` and every interview/observation
     `related_intake_id` equals `client_intake.intake_id`;
   - ids use their expected prefixes.

## Running

This machine uses `python3` (there is no bare `python`). From the repo root:

```bash
# one-time: install the dev dependency
make install-dev          # == python3 -m pip install -r requirements-dev.txt

# run both harnesses
make validate             # == validate_phase1.py + validate_phase2.py

# or run one at a time
make validate-phase1
make validate-phase2
```

Or invoke them directly, without the Makefile:

```bash
python3 tests/validate_phase1.py
python3 tests/validate_phase2.py
```

## Exit codes

Both harnesses share the same convention:

| Code | Meaning |
| --- | --- |
| `0` | All blocking checks passed. Warnings may be present (Phase 1 only). |
| `1` | A schema, example/packet conformance, or packet-referential check failed. |
| `2` | A dependency is missing (install `requirements-dev.txt`). |

The nonzero-on-failure / zero-on-warnings-only behavior makes these harnesses safe
to wire into CI later without additional tooling.

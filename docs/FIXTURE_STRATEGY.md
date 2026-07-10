# Fixture Strategy

How Peak handles test and demo data without storing any data artifacts in the
repository.

## Core rule

**No data artifacts are stored in this repo.** The repository contains **source assets
only** — Peak docs, schemas, prompt contracts, tools/scripts, tests/validation logic,
and architecture/policy materials. It does not contain committed example packets,
sample outputs, fixture JSON, inventory exports, telemetry, financial records, or
resolver capsule payloads.

## Fixtures are generated at runtime

When validation needs representative objects, they are **generated synthetically at
runtime**:

- Built in memory by [`../tests/synthetic_fixtures.py`](../tests/synthetic_fixtures.py)
  (that file is **code**, not stored data — it constructs objects programmatically).
- Written, when a file is needed, to a **temporary directory** via Python's
  `tempfile`, then **auto-deleted**. Generated fixtures are **not committed** and
  nothing persists in the repo.
- Clearly synthetic: ids and labels carry a `synthetic` marker
  (`intake_synthetic_demo`, `client_synthetic`, `pkt_synthetic_demo`, …) so they can
  never be mistaken for real records.

If a generated fixture ever needs to persist for debugging, it must go to an **ignored
local path** (`.generated/`, `.local/`, `tmp/`, `local-fixtures/`) — never to a
tracked location.

## Pseudo / demo IDs

Pseudo/demo ids are allowed **only** for:

- generated synthetic fixtures (above), or
- controlled non-repo storage (an engagement database or private resolver capsule).

They must never stand in for, or be derived from, real client data.

## Real client data

- **Real client data is never used for fixtures, examples, tests, demos, or training.**
- Real client data belongs in **controlled engagement database/storage** and, where
  appropriate, **private resolver capsules** — the data layer is that storage, **not
  Git**. See [`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md).
- Real client data is only handled for authorized live client engagement work (see
  [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md)).

## Redaction framing removed

Peak's repo policy is **not** framed around redaction. Because the repo stores no data
artifacts at all, there is nothing in it to redact. Test/demo material is **synthetic**
rather than redacted. (The former redaction guide has been **removed**.)

## What enforces this

- [`../tests/validate_phase7_policy.py`](../tests/validate_phase7_policy.py) fails if
  forbidden stored-artifact paths reappear (e.g. `examples/`, sample packets, sample
  outputs) or if redaction-policy framing is reintroduced.
- The validation harnesses read no committed example data; they generate synthetic
  fixtures in temp directories.
- [`.gitignore`](../.gitignore) ignores the local/generated paths above.

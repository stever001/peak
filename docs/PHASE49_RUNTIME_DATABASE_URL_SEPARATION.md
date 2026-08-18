# Phase 49 — Runtime Database URL Separation

**Status:** source wiring. **No production command. No production connection. No writer enabled or
invoked. No migration added. No model, table, writer, or allowlist change.**
**Baseline commit:** `4b285c55504d2317969d64e5d03ebce1dd1acd23` — *Document Phase 48 production
runtime readiness gate*
**Alembic head:** unchanged at `013_governed_identifier_collation_policy`
**Harness:** [`tests/validate_phase49_runtime_database_url_separation.py`](../tests/validate_phase49_runtime_database_url_separation.py)
(`make validate-phase49`, included in `make validate`)
**Related:** [`PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md`](PHASE48_PRODUCTION_RUNTIME_READINESS_GATE.md),
[`DATABASE_ACCESS_AND_AUDIT.md`](DATABASE_ACCESS_AND_AUDIT.md)

---

## 1. Purpose

Give application/runtime database sessions their own URL variable, so the runtime and migration
credentials cannot collapse into a single environment name.

Phase 48 verified a least-privilege runtime credential (`SELECT` + `INSERT` only) and returned
**READY** — but named one blocker: `peak/db/session.py` read `PEAK_DATABASE_URL`, so **nothing in
source consumed `PEAK_RUNTIME_DATABASE_URL`**. The only way to have wired runtime was to point it at
the migration variable, which would have handed schema-change privileges to application code. This
phase removes that as an option.

## 2. The variable split

| Variable | Read by | Role |
| --- | --- | --- |
| `PEAK_RUNTIME_DATABASE_URL` | `peak/db/session.py` | application/runtime DB sessions |
| `PEAK_DATABASE_URL` | `alembic/env.py` | Alembic / migration / bootstrap **only** |
| `PEAK_PRODUCTION_DB_URL` | `tools/production_mysql_collation_verify.py` | read-only verifier **only** |

The three code paths are disjoint. `session.py` performs exactly one environment read and it targets
the runtime constant; `alembic/env.py` names neither of the other two; the verifier never names the
runtime variable.

## 3. What changed

| File | Change |
| --- | --- |
| [`peak/db/session.py`](../peak/db/session.py) | Reads `PEAK_RUNTIME_DATABASE_URL`; adds `get_runtime_database_url()`, `create_runtime_engine()`, explicit role-name constants, and an optional `url=` override |
| `.env.example` | Documents all three variables as separate placeholders |
| `tests/validate_phase49_runtime_database_url_separation.py` | New harness |
| `Makefile` | `validate-phase49`, wired into `make validate` |
| docs | This file, plus `DATABASE_ACCESS_AND_AUDIT.md`, `DATABASE_SCAFFOLD.md`, `IMPLEMENTATION_PLAN.md` |

`alembic/env.py` and the production verifier were **not modified** — they already read the correct
variables. No migration was added, no `alembic/versions` file was touched, and no writer, model,
base, or allowlist source changed.

## 4. Fail-closed behaviour

**Runtime never falls back to `PEAK_DATABASE_URL`.** A silent fallback is exactly the failure this
phase exists to prevent: it would give application code the migration credential's schema privileges
at the moment configuration went wrong — the worst possible time.

| Situation | Result |
| --- | --- |
| `PEAK_RUNTIME_DATABASE_URL` set | used |
| Unset | `RuntimeError` naming the missing variable |
| Unset, but `PEAK_DATABASE_URL` set | still `RuntimeError` — no fallback |
| Both set | runtime variable wins; migration variable ignored |
| Explicit `url=` passed | used, no environment variable required |

The error message names **variable names only**. It contains no value and no `://` scheme, and it
states that the migration variable is not a substitute so the reader is not tempted to make it one.

## 5. Local and test paths

No fallback flag was added, because a supported explicit path already exists and is now documented:

- every controlled writer accepts `session_factory=`, and
- `create_session_factory(url=...)` / `create_runtime_engine(url=...)` accept an explicit URL.

Existing harnesses that set `PEAK_DATABASE_URL` do so to drive **Alembic** (`command.upgrade`), which
is still the correct variable for that purpose, so none of them needed changing.

## 6. Compatibility

`get_database_url()` and `create_db_engine()` remain as deprecated aliases resolving to the runtime
path, so any caller written before the split keeps working. `ENV_VAR` is retained and now names the
runtime variable. All eleven controlled writers continue to resolve sessions through
`create_session_factory()`, which is the single seam where runtime connectivity is decided — their
behaviour is otherwise untouched and they remain create-only.

## 7. What this phase does not do

- **It does not enable writers.** No writer was run, no deployment or environment configuration was
  added, and nothing was pointed at production.
- **It does not touch production.** No connection was made, no credential file was sourced or read,
  and the read-only verifier was never run with real credentials.
- **A separately approved enablement phase is still required** before application writers connect to
  production. This phase only makes it *possible* to wire runtime without violating credential
  separation.

## 8. Security confirmations

- **No DSNs, hosts, usernames, passwords, tokens, certificate paths, database names, connection
  URLs, environment values, or row values** were added to source, tests, or docs. `.env.example`
  carries placeholders only.
- No operator credential file is referenced by any shipped source file, and none was sourced, read,
  displayed, or searched. `.env` was not read; no secret store was searched.
- The harness runs fully offline: it opens no database connection, scrubs all three role variables
  from child environments before probing behaviour, and only ever points a child at an explicit
  SQLite URL.

---

**Follow-up:** the runtime path introduced here was exercised against the real runtime credential in
**Phase 50** — see
[`PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md`](PHASE50_CONTROLLED_RUNTIME_CONNECTIVITY_GATE.md).
That phase adds a reusable read-only gate (`make runtime-connectivity-gate`) that connects through
`create_runtime_engine`, confirms the `SELECT` + `INSERT` posture, and still writes nothing and reads
no application table. Writer enablement remains a separately approved phase.

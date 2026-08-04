# Managed MySQL Production-Parity Validation (Phase 41)

**Status:** implemented (validation tooling and documentation only — no schema, no writer, no
migration).
**Tool:** [`tools/managed_mysql_parity_check.py`](../tools/managed_mysql_parity_check.py)
**Harness:** [`tests/validate_phase41_managed_mysql_production_parity.py`](../tests/validate_phase41_managed_mysql_production_parity.py)
(`make validate-phase41`)
**Offline target:** `make mysql-parity-static` — **Opt-in target:** `make mysql-parity-staging`

---

## Why this phase exists

Phase 38 produced a concrete, reproducible defect that every local test suite passed.

MySQL enforces a **64-character limit on identifiers** — table, index, and constraint names.
**SQLite does not.** Phase 38's convention-derived index name would have been:

```
ix_internal_report_review_packets_internal_assessment_report_draft_id     <- 69 characters
```

That name is silently accepted by SQLite. Against managed MySQL, `alembic upgrade head` would have
failed outright. Phase 39's convention-derived names were worse — up to **78** characters:

```
ix_internal_report_review_packet_decisions_internal_assessment_report_draft_id   <- 78 characters
```

Both were caught by hand and fixed with short explicit prefixes (`ix_internal_report_review_packets_report_draft`,
`ix_irrpd_*`). Catching them by hand is not a control. **Phase 41 turns that lesson into an
automated, repeatable check** so the next long table name cannot reach managed MySQL untested.

Those two overlong names are deliberately quoted in the model and migration comments as cautionary
examples. The parity checker distinguishes *documenting* a bad identifier from *using* one: it
scans executable code and identifier-shaped string literals, never prose.

---

## SQLite structural smoke vs. managed MySQL production parity

| | Local SQLite smoke | Managed MySQL production parity |
| --- | --- | --- |
| Runs in `make validate` | Yes | **No** — opt-in only |
| Needs credentials / network | No | Yes (out-of-band) |
| Proves schema *shape* | Yes | Yes |
| Proves identifier length limits | **No** | Yes |
| Proves collation / comparison semantics | **No** | Yes |
| Proves charset behavior | **No** | Yes |
| Proves constraint enforcement strictness | Partly | Yes |
| Proves concurrency / locking behavior | **No** | Yes |
| Production-readiness proof path | **No** | **Yes** |

**SQLite is not the production-readiness proof path.** It is a fast structural smoke path. A green
SQLite run is necessary but not sufficient. **Managed MySQL test/staging validation is required**
before treating DB-backed functionality as production-ready.

### What standard validation *does* prove

`make validate` (which includes `make mysql-parity-static`) proves, with no credentials and no
network:

- Every **ORM model** table, column, index, and constraint identifier fits 64 characters.
- Every identifier each **migration would actually send to MySQL** fits 64 characters — including
  names built at runtime from f-strings over module constants, which source text cannot resolve.
- No indexed column silently relies on a convention-derived name that would overflow.
- The two known overlong Phase 38/39 identifiers are not used as real identifiers.
- Every created table pins `InnoDB` + `utf8mb4`; no legacy 3-byte `utf8`.
- The migration chain is linear, has exactly one base and one head, and the head is pinned at
  `012_internal_report_review_packet_decisions`.
- No migration contains `INSERT` / seed / `bulk_insert` / `op.execute` / arbitrary SQL.
- Migrations use only `create_table`, `create_index`, `drop_index`, `drop_table`, `add_column`,
  `drop_column`.
- No destructive operation appears in any `upgrade()`.
- Every `downgrade()` is scoped to exactly the objects its own `upgrade()` created — proven by
  simulation, not guessed from text.

### What standard validation does **not** prove

It cannot, even in principle, prove any of the following without a real MySQL server:

- The **effective collation** of the managed database and therefore the case/accent sensitivity of
  every comparison (see the open gap below).
- That MySQL accepts the applied index/constraint set at `upgrade head` time.
- Strict-mode behavior, implicit type coercion, or truncation semantics.
- Row-format / index-prefix-length limits under a given `innodb_large_prefix` configuration.
- Concurrency, locking, deadlock, or transaction isolation behavior.

Those belong to the opt-in staging pass.

---

## Open parity gap: no collation is pinned

**This is a real finding, reported rather than silently patched.**

Nothing in `peak/db/base.py`, `peak/db/models.py`, or any migration pins a collation. Every created
table declares `mysql_charset="utf8mb4"` and `mysql_engine="InnoDB"` — and nothing more. That means
**the managed server's default collation decides comparison semantics.**

- MySQL 8's default collation for `utf8mb4` is `utf8mb4_0900_ai_ci` — **accent-insensitive and
  case-insensitive**.
- The local SQLite smoke path compares `String` columns **case-sensitively**.

So the two validation layers can disagree, and the disagreement lands on identity and idempotency:

| Column class | Columns |
| --- | --- |
| Record identity | `id`, `owner_id`, `client_id`, `engagement_id` |
| Authorization | `authorization_scope` |
| Idempotency / integrity | `idempotency_key`, `payload_fingerprint`, `plan_fingerprint`, `report_draft_payload_fingerprint`, `packet_payload_fingerprint`, `packet_hash` |

**Concrete consequence if the managed default is case-insensitive:** the
`UNIQUE (owner_id, client_id, engagement_id, idempotency_key)` boundary carried by every controlled
writer would treat `idem-key-1` and `idem-KEY-1` as the **same key**. Two writes intended to be
distinct would collapse into one idempotent replay. The reverse also holds: identity/scope matching
that is case-sensitive under SQLite tests would be case-insensitive in production.

**Why no migration is proposed here.** Phase 41 is a validation phase and does not invent schema.
Whether this is a live defect depends on the managed server's configured default collation, which
**cannot be determined by reading the repository**. It requires a managed MySQL runtime check. The
static checker therefore reports it as a `WARN`, not a `FAIL` — failing the build on an
unconfirmed, pre-existing condition would convert a finding into a broken build without adding
information.

**Resolution path (requires separate approval, not done in this phase):**

1. Run `make mysql-parity-staging` against a disposable schema to read back the effective collation.
2. If it is case-insensitive, decide deliberately whether the governed identifier columns should be
   pinned to a deterministic collation (`utf8mb4_bin` or `utf8mb4_0900_as_cs`).
3. If so, that is a **new migration in its own phase**, with its own review — not a silent edit.

---

## Running the checks

### Offline (default; part of `make validate`)

```bash
make mysql-parity-static                          # source + simulation tiers
make mysql-parity-static PYTHON=.venv/bin/python  # adds model introspection + full simulation
```

No credentials, no network, no DNS, no TLS, no `.env`, no DSN, no database. Safe on a laptop with
no managed DB access. Without SQLAlchemy/Alembic installed it still runs the source tier and
reports which deeper checks were skipped — it never pretends to have checked more than it did.

### Opt-in disposable staging (never part of `make validate`)

```bash
make mysql-parity-staging                          # skips safely with no configuration
```

With no configuration it prints a sanitized skip and **exits 0**, having attempted no network,
imported no database driver, and read no `.env`.

To run it later, both markers are required:

```bash
export PEAK_MANAGED_MYSQL_TEST_DSN=...     # out-of-band; never committed, never printed
export PEAK_MANAGED_MYSQL_DISPOSABLE=1     # or pass --staging-target-is-disposable
```

The tool **fails closed**:

| Condition | Behavior | Exit |
| --- | --- | --- |
| No DSN, no disposable marker | Sanitized skip; nothing attempted | 0 |
| DSN present, **not** marked disposable | **REFUSED** — will not connect | 2 |
| Marked disposable, no DSN | Skip; nothing attempted | 0 |
| `--env prod` | **REFUSED** — production is never selectable | 2 |
| Both markers present | **HOLD** — a live run needs separate explicit approval | 0 |

**A live run is not executed by Phase 41.** The gate is shipped; running it against a specific
disposable target is a separate, explicitly approved action.

---

## Policy

- **The production DB is not a smoke-test target.** `--env prod` is refused, fail-closed. Production
  DSNs exist for operations only.
- **No client data, ever.** Parity validation runs against an empty disposable schema. Never a copy
  of client data, never a pseudo-client fixture, never a production snapshot.
- **No production write path, no cleanup path, no delete path** is added by this phase, and none
  exists in the repo.
- **Migration downgrade/re-upgrade is never run against a production client-data DB.**
- **Credentials are never committed and never printed.** DSNs come only from environment variables,
  never from Git and never from `.env` in validation. The tool prints `configured (value hidden)` —
  never the value.
- **Every output line is sanitized.** DSN-shaped strings, `password=`/`token=`/`api_key=` pairs,
  `user:pass@host` forms, and PEM certificate/key blocks are replaced with `[secret withheld]` before
  printing. Failures are reported by exception **type** only, because exception messages routinely
  embed the DSN that caused them.

## Boundaries

Managed MySQL validation is **separate from** and touches none of: AgentNet publication, MCP or
resolver calls, LLM or mock-LLM calls, agent or mock-agent execution, client-facing output,
approval workflows, financial/ROI verification, and capsule publication. Phase 41 adds no table,
model, migration, allowlist pair, writer, generic CRUD, or arbitrary SQL executor.

The managed-MySQL rubric ([`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md)),
Client Isolation Option A ([`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md)), and the
Peak-operated AgentNet publication policy
([`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md))
are unchanged by this phase.

## Related

- [PRODUCTION_PARITY_DB_VALIDATION.md](PRODUCTION_PARITY_DB_VALIDATION.md) — the two-layer model (Phase 34)
- [MANAGED_MYSQL_PERSISTENCE_RUBRIC.md](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) — managed remote MySQL as the operational store
- [`tools/managed_mysql_check.py`](../tools/managed_mysql_check.py) — the Phase 34 runbook/connectivity helper this checker complements

---

## Phase 42 — the collation gap, classified

Phase 41 reported the unpinned-collation gap as a single warning over a hand-written column list.
Phase 42 replaced that with a deterministic classification of **all 308 string columns across all
18 tables** — see [`GOVERNED_MYSQL_COLLATION_POLICY.md`](GOVERNED_MYSQL_COLLATION_POLICY.md) and
`make mysql-collation-audit`.

Result: **211 governed columns** (45 distinct names) require deterministic comparison, **none**
pins a collation, and **62 of them sit inside a UNIQUE constraint or primary key**. The status is
`NEEDS_REMEDIATION`.

Two corrections to this document's Phase 41 framing:

- `packet_hash` was listed among comparison-sensitive **columns**. It is not a column — it is a
  Phase 23 ingestion-draft field folded into `details_json`, so it carries no collation. The audit
  now asserts it stays a non-column.
- Enum/status columns are **lower** priority than first implied: controlled writers gate them
  against closed vocabularies with case-sensitive Python membership tests, so a case variant cannot
  be persisted. `idempotency_key` has no such mitigation — it is stored verbatim.

Remediation is candidate migration `013`, documented but **not implemented**; it requires explicit
approval and managed-MySQL staging verification first.

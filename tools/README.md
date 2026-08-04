# Tools

Local, human-in-the-loop helpers for Peak consultants. **Not an agent runtime.**
Nothing here calls an LLM, an API, AgentNet, or an agent, and nothing is stored.

**Database access is offline by default and opt-in by exception.** `packet_runner.py` and
`managed_mysql_parity_check.py --mode static` (the default mode) open no database connection and
make no network call at all — they are safe with no credentials. Two paths *can* reach a managed
database, and both are explicit, credential-free by default, skip safely with no configuration, and
are excluded from `make validate`: `managed_mysql_check.py --connect` (read-only `SELECT 1`) and
`managed_mysql_parity_check.py --mode staging`. Neither ever prints a DSN, and neither is selectable
against production.

Since Phase 43 one tool *is* pointed at production, deliberately and read-only:
`production_mysql_collation_verify.py`. It issues only hard-coded `SELECT`/`SHOW` metadata queries,
performs no schema mutation, data write, migration, or cleanup, and fails closed without an explicit
read-only affirmation.

## `packet_runner.py`

A read-only helper that takes an `EngagementPacket` and orients a consultant toward the
right prompt contracts. It does **not** run the workflow — the consultant runs the LLM
by hand and owns the output.

```bash
# A real packet from controlled engagement storage (not the repo):
python3 tools/packet_runner.py --packet /path/to/engagement-packet.json

# Via the Makefile (PACKET is required):
make packet-summary PACKET=/path/to/engagement-packet.json
```

`--packet` is **required** — there is no demo or sample mode. The repo stores no
packet; point `--packet` at a real packet held in controlled engagement storage (an
authorized engagement workspace). Tests may pass a temporary synthetic fixture file,
but that is test-only, not a workflow feature.

### What it does
1. Loads the packet JSON from the `--packet` path.
2. Runs a lightweight structural check.
3. Prints a consultant-readable summary: `packet_id`, `engagement_label`,
   `assessment_stage`, client organization, inventory environment, known systems, and
   counts of evidence / interviews / visual / workflow observations.
4. Lists the available prompt contracts by workflow (intake → … → learning).
5. Prints next-step instructions: open the contract, paste the packet JSON into its
   reusable body, review, and save the reviewed output to controlled engagement storage
   (not the repo).

### What it explicitly does NOT do
- No LLM call.
- No AgentNet lookup (AgentNet is intended future grounding architecture, not
  integrated).
- No client-facing output generated automatically.
- No API, database, or network request.
- **No packet written, stored, or committed** — the runner only reads and prints.

### Exit codes
| Code | Meaning |
| --- | --- |
| `0` | Packet loaded/summarized (structural check passed). |
| `1` | Packet missing, invalid JSON, or failed the structural check. |
| `2` | Bad CLI usage (`--packet` missing). |

### Tested by
`tests/validate_phase5_runner.py` (stdlib-only), part of `make validate`.

---

## `managed_mysql_check.py`

The Phase 34 managed-MySQL runbook / connectivity helper. Prints the rubric runbook for a managed
`test`/`staging` environment; refuses `prod`; skips cleanly (exit 0) with no DSN configured. Only
with an explicit `--connect` **and** a DSN present does it open a read-only `SELECT 1`. It performs
no write, seed, delete, cleanup, or migration, and never prints the DSN.

```bash
make db-check-managed-test           # rubric check   (skips with guidance if no DSN)
make managed-mysql-smoke             # smoke runbook  (skips with guidance if no DSN)
make managed-mysql-migration-check   # migration runbook (skips with guidance if no DSN)
```

---

## `managed_mysql_parity_check.py`

The Phase 41 production-parity checker. Enforces the MySQL assumptions the local SQLite smoke path
cannot — most concretely MySQL's **64-character identifier limit**, which SQLite silently accepts
and which produced a real 69-character defect in Phase 38.

```bash
make mysql-parity-static                          # offline: no credentials, network, .env, or DSN
make mysql-parity-static PYTHON=.venv/bin/python  # adds model introspection + migration simulation
make mysql-parity-staging                         # opt-in; skips safely with no disposable target
```

**Static mode (default) is fully offline.** Because migrations build identifiers at runtime
(f-strings over module constants), source text cannot reveal the names MySQL would receive — so the
checker *simulates* each migration's `upgrade()`/`downgrade()` against a recording stand-in for
`op` that executes no SQL and opens no connection. It also checks migration chain linearity, the
pinned head, schema-only migration policy, bounded downgrades, and `InnoDB`/`utf8mb4` pinning, and
reports the open **collation** gap as a warning.

**Staging mode fails closed.** It refuses `--env prod`, refuses a DSN that is not marked disposable,
and skips (exit 0) with no configuration — importing no database driver and reading no `.env`. A
live run requires separate explicit approval of a specific disposable target.

See [`../docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md`](../docs/MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md).

---

## `governed_mysql_collation_audit.py`

The Phase 42 governed-collation audit. Classifies every string column in the controlled schema by
**what its comparisons decide** — identity, authorization, uniqueness, integrity, or nothing — and
reports which governed columns still inherit their collation from the managed server.

```bash
make mysql-collation-audit                          # offline; no credentials, network, .env, or DSN
make mysql-collation-audit PYTHON=.venv/bin/python  # full model introspection (authoritative)
```

Fully offline: it opens no database connection, imports no MySQL driver, reads no `.env`, and
prints no DSN. Without SQLAlchemy it falls back to a source scan and **declares itself
non-authoritative** rather than drawing a conclusion it cannot support.

It exits **0** while reporting `NEEDS_REMEDIATION` — the unpinned-collation finding is a known,
documented open item, not a build failure. It exits **1** only if the audit itself is broken: a
required governed column missing or misclassified, so a future refactor cannot silently drop a
column out of governed scope.

It proposes no schema and writes no migration. See
[`../docs/GOVERNED_MYSQL_COLLATION_POLICY.md`](../docs/GOVERNED_MYSQL_COLLATION_POLICY.md).

---

## `production_mysql_collation_verify.py`

The Phase 43 **read-only** production collation verification tool. Answers the question Phase 42
could not settle from source: is the collation risk live in the real deployed database?

```bash
make production-mysql-collation-verify                          # skips safely if unconfigured
make production-mysql-collation-verify PYTHON=.venv/bin/python  # SQLAlchemy needed to connect
```

Requires **two** environment variables, supplied out-of-band (names only shown here; values are
never printed): `PEAK_PRODUCTION_DB_URL` (or `PEAK_DATABASE_URL`) and
`PEAK_PRODUCTION_DB_READONLY_CONFIRM=1`. Optional: `--collision-probe` (bounded `COUNT`-only
aggregates) and `--verbose` (query *names* only).

**Read-only by construction.** Every statement is a hard-coded constant in a query allowlist;
`assert_read_only()` runs before each execution and again at the driver boundary. No code path
accepts SQL from a caller. `INSERT`/`UPDATE`/`DELETE`/`ALTER`/`DROP`/`TRUNCATE`/`CREATE`/`GRANT`/
`REVOKE`/`LOCK`/`CALL`/`LOAD`/`OUTFILE`/`SET`, multi-statement execution, and migration execution
are all unreachable.

**Fails closed.** Unconfigured → skip (exit 0), no driver imported, no `.env` read. Connection
setting without the affirmation → **REFUSED** (exit 2), no connection attempted.

**No secrets, no row values.** Never prints a DSN, host, user, password, token, cert, or
environment value; never emits a production row value. Failures report the exception *type* only.

It recommends; it never acts. Migration `013` is not created or executed. See
[`../docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](../docs/PRODUCTION_MYSQL_COLLATION_VERIFICATION.md).

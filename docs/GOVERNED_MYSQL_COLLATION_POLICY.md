# Governed MySQL Collation Policy (Phase 42)

**Status:** policy and remediation plan. **No schema change was made.** No migration exists.
**Audit tool:** [`tools/governed_mysql_collation_audit.py`](../tools/governed_mysql_collation_audit.py)
(`make mysql-collation-audit`)
**Harness:** [`tests/validate_phase42_governed_mysql_collation_policy.py`](../tests/validate_phase42_governed_mysql_collation_policy.py)
(`make validate-phase42`)

---

## Why this phase exists

Phase 41 found that **no collation is pinned anywhere** in the repository. Every table declares
`mysql_charset="utf8mb4"` and `mysql_engine="InnoDB"` and nothing more, so the **managed server's
default collation decides comparison semantics**. MySQL 8 defaults `utf8mb4` to
`utf8mb4_0900_ai_ci` — accent- **and** case-**insensitive**. The local SQLite smoke path compares
case-**sensitively**. The two validation layers can therefore disagree about whether two values are
the same value.

Phase 41 reported that as one warning over a hand-written column list. Phase 42 makes it precise:
every string column is classified by what its comparisons actually *decide*, so remediation can be
scoped to the columns that matter rather than applied blindly to all 308.

**Phase 42 classifies and plans. It does not patch.** Remediation is migration `013`, and it
requires explicit approval before implementation.

---

## Policy classes

| Class | Comparison requirement | Meaning |
| --- | --- | --- |
| `governed_identifier` | **Deterministic (case-sensitive) required** | Primary keys, tenant/engagement identity, record refs, actor refs |
| `governed_scope` | **Deterministic required** | Authorization scope, audience, data/sensitivity class |
| `governed_idempotency` | **Deterministic required** | `idempotency_key` — the controlled-writer replay boundary |
| `governed_hash_or_fingerprint` | **Deterministic required** | sha256 payload/plan fingerprints and content hashes |
| `governed_security_token_or_secret_hash` | **Deterministic required** | Token/secret-hash columns (none exist today; the class is pre-declared) |
| `governed_enum_status` | Deterministic **preferred** | Closed-vocabulary status/intent/type/role labels |
| `ordinary_text` | Server default acceptable | Human-facing prose: summaries, labels, descriptors |
| `json_or_details_text` | Server default acceptable | JSON/`Text` detail; must never carry an equality boundary |
| `unknown_governed_candidate` | **Human review required** | Anything the classifier cannot place |

### The rule that matters

> **A column whose comparison decides identity, authorization, uniqueness, or integrity
> must not inherit its collation from the server.**

Put the other way round: **server-default collation is insufficient for governed equality
boundaries.** It is acceptable only where a comparison decides nothing.

Ordinary prose may. JSON detail may — but only because it must never participate in an equality,
uniqueness, or authorization decision in the first place.

### Why `governed_enum_status` is "preferred", not "required"

Enum-like columns (`review_status`, `decision_intent`, `packet_status`, …) are gated *before*
persistence by closed-vocabulary membership tests in Python (`intent not in
ALLOWED_DECISION_INTENTS` and similar), and Python string membership is case-sensitive. A
case-variant value therefore cannot reach the database through a controlled writer. That is a real
mitigation, so these columns rank below the governed classes — but it is an **application-layer**
mitigation, which is why deterministic collation remains preferred rather than dismissed.

No such mitigation exists for `idempotency_key`: writers accept any caller string matching
`^[A-Za-z0-9_.:/\-]{1,128}$` and persist it **verbatim, with no case normalization**.

---

## Current-state assessment

Produced by `make mysql-collation-audit PYTHON=.venv/bin/python` against the live model metadata:

| Measure | Count |
| --- | --- |
| Tables inspected | 18 |
| String/`Text` columns audited | 308 |
| Columns pinning an explicit collation | **0** |
| Governed columns requiring deterministic comparison | **211** (45 distinct names) |
| — of those, with explicit collation | **0** |
| — **CRITICAL** (in a UNIQUE constraint / primary key) | **62** |
| — **HIGH** (indexed equality path) | **76** |
| — **MEDIUM** (governed, not indexed) | **73** |
| `governed_enum_status` (deterministic preferred) | 85 |
| `ordinary_text` | 9 |
| `json_or_details_text` | 3 |
| Unclassified | 0 |

**Verdict: `NEEDS_REMEDIATION`.** Every governed column in the controlled schema currently defers
its comparison semantics to the managed server's default collation.

### Highest-risk boundary

```
UNIQUE (owner_id, client_id, engagement_id, idempotency_key)
```

enforced on **11 tables**: `agent_run_records`, `agent_task_queue_records`, `evidence_references`,
`intake_note_records`, `internal_assessment_report_drafts`,
`internal_report_review_packet_decisions`, `internal_report_review_packets`,
`internal_reviewer_decision_records`, `review_bundle_records`, `review_records`,
`source_ingestion_records`.

Under a case-insensitive server default, `idem-key-1` and `idem-KEY-1` are **one key**. Two
intentionally distinct writes collapse into an idempotent replay, or a legitimately new write is
rejected as an idempotency conflict. Because writers persist the key verbatim, nothing upstream
mitigates this.

The same collation also governs `owner_id`, `client_id`, and `engagement_id` — so tenant and
engagement identity matching would become case-insensitive in production while remaining
case-sensitive in every local test.

### A distinction worth keeping explicit

`packet_hash` is **not a column**. It is a Phase 23 ingestion-draft field that the source-ingestion
writer folds into `details_json`. It therefore has no collation, correctly — but it also must never
be promoted into an equality or uniqueness boundary without first becoming a real column with an
explicit collation. The audit asserts it is still not a column, so this cannot rot into a silent
assumption. (Phase 41's tool listed it among comparison-sensitive *columns*; that has been
corrected.)

---

## Recommended policy

1. **Governed identifier / scope / idempotency / hash / security columns must pin a deterministic,
   case-sensitive collation explicitly.** Never rely on the server default.
2. **Ordinary descriptive text does not need a binary collation.** Case-insensitive comparison is
   appropriate for human-facing prose.
3. **JSON/detail text must not participate in uniqueness or authorization decisions.** If a value
   inside `details_json` ever needs an equality boundary, promote it to a real, explicitly collated
   column first.
4. **Enum/status columns** must either keep their pre-persistence closed-vocabulary normalization
   (current behavior) or adopt deterministic collation — preferably both.
5. **Every future migration that adds a governed string column must state its collation
   explicitly.** Silence is not an acceptable default. This is the durable rule Phase 42 adds.

### Candidate collation — alternatives documented, selection deferred

The repository does not pin a MySQL major version anywhere, so this document deliberately does
**not** declare a final selection.

| Candidate | Properties | Fit |
| --- | --- | --- |
| `utf8mb4_bin` | Byte-exact; case- and accent-sensitive; MySQL 5.7 and 8.x | **Leading candidate** for opaque governed identifiers |
| `utf8mb4_0900_as_cs` | Unicode-aware, case- and accent-sensitive; **MySQL 8.0+ only** | Better where human-readable ordering matters |
| `VARBINARY` / `BINARY` column types | Byte semantics, not character semantics | Rejected — a larger semantic change than the problem requires |

`utf8mb4_bin` leads because governed values are **ASCII by construction**: refs are constrained to
`^[A-Za-z0-9_.:/\-]{1,128}$` by the writers, and fingerprints to `[0-9a-f]{64}`. Unicode-aware
ordering buys nothing for values that cannot contain non-ASCII characters, and byte comparison is
the strictest available guarantee.

**Final selection requires confirming the managed server's version and effective default
collation**, which cannot be read from this repository. See the verification steps below.

---

## Existing migration analysis

**No prior migration attempted collation hardening — not partially, not comprehensively.** A repo
scan for `mysql_collate`, `COLLATE`, `utf8mb4_*`, and `BINARY` across all 12 migrations,
`peak/db/models.py`, and `peak/db/base.py` returns nothing.

Migrations `002`–`005` are named "idempotency" migrations, which could be mistaken for hardening.
They are not: they add the `idempotency_key` / `payload_fingerprint` **columns** and the composite
UNIQUE index, and pin no collation on any of them. So the idempotency boundary was created
correctly in structure and left entirely dependent on the server default for semantics.

**Consequence for remediation:** every governed column across all 18 tables is unresolved, and the
remediation must be **additive `ALTER`-only**. Existing migrations must not be rewritten — they are
already applied wherever this schema has been deployed, and editing applied history would make the
repo disagree with reality.

---

## Candidate migration `013` — plan only, NOT implemented

> **No file `alembic/versions/013_*.py` exists, and none may be created without explicit
> approval.** The Phase 42 harness asserts its absence.

**Candidate name:** `013_governed_identifier_collation_policy`
**Parent:** `012_internal_report_review_packet_decisions`

### Scope

- **Affected tables:** all 18.
- **Affected columns:** the 211 governed column instances (45 distinct names). Prioritized:
  1. **CRITICAL (62)** — `id`, `owner_id`, `client_id`, `engagement_id`, `idempotency_key`
     wherever they participate in a primary key or the composite UNIQUE index.
  2. **HIGH (76)** — indexed governed columns: `authorization_scope`, `agent_run_id`, `audience`,
     `plan_fingerprint`, `report_plan_id`, the `*_record_id` / `*_reference_id` refs, and similar.
  3. **MEDIUM (73)** — remaining governed columns: `payload_fingerprint`, `created_by`,
     `updated_by`, `requested_by`, `reviewer_ref`, and similar.
- **Change per column:** `ALTER TABLE … MODIFY <col> VARCHAR(<existing length>) CHARACTER SET
  utf8mb4 COLLATE <selected deterministic collation>` — **length and nullability unchanged**.
- **Explicitly out of scope:** `ordinary_text`, `json_or_details_text`, and (pending the decision
  in policy rule 4) `governed_enum_status`.

### Uniqueness and index implications

- A collation change **does not alter stored byte length**, so index key sizes are unaffected.
- The widest affected index is the composite UNIQUE
  `(owner_id[128] + client_id[64] + engagement_id[64] + idempotency_key[128])` = 384 characters ×
  4 bytes = **1536 bytes**, within InnoDB's 3072-byte limit for `DYNAMIC` row format. No index
  needs shortening.
- **MySQL may rebuild indexes** on the affected columns. On a populated table this is a blocking or
  online-DDL operation depending on server version and configuration — it must be timed
  deliberately, not run casually.
- **Direction matters, and it is the safe direction** *(corrected in Phase 43)*. Moving from a
  case-**insensitive** collation to a case-**sensitive** one makes the unique index *more*
  discriminating: values that previously collided become distinct. Every existing row was already
  unique under the looser rule, so it remains unique under the stricter one. **This direction
  cannot produce new duplicate-key violations.** (The reverse — sensitive to insensitive — could,
  which is why it is not the remediation.)
- **The real behavioral change** is that lookups become case-sensitive. Any caller that previously
  relied on `owner_id`, `client_id`, `engagement_id`, or `idempotency_key` matching in a different
  case will stop matching. Peak's writers persist and compare these verbatim, so no such reliance
  is expected — but production verification should confirm it rather than assume it.

### Downgrade posture

The downgrade restores the prior state by reverting the affected columns to the **server default
collation** — it does not attempt to reconstruct a specific prior collation, because none was ever
pinned. The downgrade is therefore honest but lossy in intent, and should be treated as a rollback
of last resort rather than a routine reversal.

### Managed MySQL staging verification (required before implementation)

1. Run `make mysql-parity-staging` against a **disposable** test/staging schema to read back the
   server's version and effective default collation. Until this is done, the defect is *probable*,
   not confirmed.
2. Apply migrations to head on an **empty disposable** schema and confirm the `ALTER` set applies
   cleanly.
3. Confirm no index exceeds byte limits after the change.
4. Scan for governed values differing only by case. Under a case-insensitive collation the unique
   index already prevents them on the boundary columns, so the informative target is governed
   columns *outside* a unique constraint, where case variants can coexist and equality lookups
   would change behavior.
5. Verify each controlled writer's authorized-create, idempotent-replay, and conflict paths still
   behave identically.
6. Confirm the Alembic head remains single and linear after `upgrade` and after `downgrade` +
   re-`upgrade`.

### Safety constraints

- **The production DB is not a smoke-test target.** Migration `013` must be validated against
  managed test/staging first. `--env prod` is refused, fail-closed, by both parity tools.
- **No client data.** Verification runs against an empty disposable schema — never a copy of client
  data, never a production snapshot, never a pseudo-client fixture.
- **No seed data** is created by the migration or its verification.
- **Backup and rollback:** take a verified backup of any populated environment before applying and
  confirm restore works. The uniqueness direction is safe (above), but an `ALTER` that rebuilds
  indexes on populated tables can still fail part-way for unrelated reasons — disk, timeout, or
  lock contention — so a tested restore path is required regardless.
- **Approval required.** Migration `013` must not be implemented until the user explicitly approves
  both the remediation and the specific collation selected.

---

## Running the audit

```bash
make mysql-collation-audit                          # offline; no credentials, no network
make mysql-collation-audit PYTHON=.venv/bin/python  # full model introspection (authoritative)
```

The audit is **offline**: no credentials, no network, no DNS, no TLS, no `.env` read, no DSN, no
database connection, and no DB driver import. Without SQLAlchemy it falls back to a source scan and
**declares itself non-authoritative** rather than drawing a policy conclusion it cannot support.

It exits **0** while reporting `NEEDS_REMEDIATION`: a known, documented open finding is not a build
failure. It exits **1** only if the audit itself is broken — a required governed column missing or
misclassified — so a future refactor cannot silently drop a column out of governed scope.

## Boundaries

Phase 42 adds no table, model, migration, allowlist pair, writer, generic CRUD, or SQL executor,
and connects to no database. It touches none of: AgentNet publication, MCP/resolver calls, LLM or
agent execution, client-facing output, approval workflows, financial verification, or capsule
publication.

The managed-MySQL rubric ([`MANAGED_MYSQL_PERSISTENCE_RUBRIC.md`](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md)),
Client Isolation Option A ([`CLIENT_ISOLATION_MODEL.md`](CLIENT_ISOLATION_MODEL.md)), and the
Peak-operated AgentNet publication policy
([`PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md`](PEAK_OPERATED_AGENTNET_PUBLICATION_POLICY.md))
are unchanged.

## Related

- [MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md](MANAGED_MYSQL_PRODUCTION_PARITY_VALIDATION.md) — Phase 41, where the gap was found
- [PRODUCTION_PARITY_DB_VALIDATION.md](PRODUCTION_PARITY_DB_VALIDATION.md) — the two-layer validation model
- [MANAGED_MYSQL_PERSISTENCE_RUBRIC.md](MANAGED_MYSQL_PERSISTENCE_RUBRIC.md) — managed remote MySQL as the operational store
- [CONTROLLED_DB_WRITER_BOUNDARY.md](CONTROLLED_DB_WRITER_BOUNDARY.md) — the eleven narrow writers whose idempotency boundary is at risk

---

## Phase 43 — verifying this policy against production

This document specifies the policy and the candidate migration. Phase 43 adds the read-only tool
that determines whether the risk is **live** in the real deployed database:
`make production-mysql-collation-verify`
([`PRODUCTION_MYSQL_COLLATION_VERIFICATION.md`](PRODUCTION_MYSQL_COLLATION_VERIFICATION.md)).

Its outcome drives the go/no-go decision for migration `013`:

- `verified_risk_live_remediation_required` → **GO**, subject to approval, a tested restore, a
  maintenance window, and a rehearsal.
- `verified_safe_no_remediation_required` → **NO-GO**; keep policy rule 5 for future columns.
- `verified_inconclusive` → **NO-GO for now**; never migrate on inconclusive evidence.

Migration `013` remains unimplemented. Phase 43 does not create, propose as code, or execute it.

---

## Phase 44 — the policy is now implemented in source control

Migration **`013_governed_identifier_collation_policy`** and the matching model metadata pin
**`utf8mb4_bin`** on all **211 governed columns** across 18 tables. The candidate plan above is no
longer a plan; it is committed code. Two things did **not** change: no table, model entity, or
allowlist pair was added, and **production has not been migrated**.

### Selection: `utf8mb4_bin`

Chosen over `utf8mb4_0900_as_cs` because governed values are ASCII by construction — refs match
`[A-Za-z0-9_.:/-]`, fingerprints are sha256 hex — so Unicode-aware ordering buys nothing, byte
comparison is the strictest guarantee, and `utf8mb4_bin` works on MySQL 5.7 as well as 8.x.
`utf8mb4_0900_as_cs` remains documented as the MySQL 8-only alternative; it was not selected.

### How the collation is attached — and why not the obvious way

Model columns use `peak.db.base.GovernedString`, which applies the collation through a MySQL
`with_variant` rather than `String(length, collation=...)`.

This is not stylistic. A bare `collation=` renders `COLLATE utf8mb4_bin` on **every** dialect, and
SQLite — which backs a dozen local structural-smoke harnesses — rejects it outright with
`no such collation sequence: utf8mb4_bin`. The variant emits **identical MySQL DDL** while leaving
SQLite untouched, so local validation stays honest instead of being disabled to accommodate the
change.

### Scope: exactly the deterministic-required classes

| Class | Columns | In migration 013 |
| --- | --- | --- |
| `governed_identifier` | 156 | **yes** |
| `governed_scope` | 27 | **yes** |
| `governed_hash_or_fingerprint` | 17 | **yes** |
| `governed_idempotency` | 11 | **yes** |
| `governed_enum_status` | 85 | no — see below |
| `ordinary_text` | 9 | no |
| `json_or_details_text` | 3 | no |

`governed_enum_status` is deliberately excluded. The Phase 42 audit classifies it as
deterministic-**preferred**, not required: controlled writers gate those values against closed
vocabularies with case-sensitive Python membership tests, so a case variant cannot be persisted in
the first place. Including them would have exceeded the 211-column scope this phase was authorised
for. They remain candidates for a later, separately justified phase.

### What source control now proves — and what it does not

`make mysql-collation-audit PYTHON=.venv/bin/python` now reports
**`MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED`** rather than `NEEDS_REMEDIATION`. Read that
status precisely:

- **Satisfied:** every governed column pins a deterministic collation in the models and migration.
- **Unverified:** the deployed database has **not** been migrated. Migration `013` has not been
  executed against production, and standard offline validation can never prove otherwise.

Only `make production-mysql-collation-verify` can read production's effective collation — before
migration execution to confirm the risk, and again afterwards to confirm the fix.

## Production execution checklist (later, separately approved)

Migration `013` exists in source control. Running it against production is a **separate approved
operation** and was not performed in Phase 44.

1. **Verify first.** Run `make production-mysql-collation-verify` and record the sanitized outcome.
   If it reports `verified_safe_no_remediation_required`, production is already deterministic and
   no execution is needed.
2. **Obtain explicit approval** for both the execution and the selected collation.
3. **Take a backup and test the restore.** A backup whose restore has not been exercised is not a
   rollback plan.
4. **Rehearse** on a disposable schema restored from a production-shaped backup, timing the ALTERs.
5. **Size a maintenance window.** MySQL may rebuild indexes on the affected columns; on populated
   tables this is a blocking or online-DDL operation depending on server version and configuration.
6. **Execute** `alembic upgrade head` against production through the approved operational path —
   never from a test harness, an agent, or a worker.
7. **Verify again.** Re-run `make production-mysql-collation-verify` and confirm
   `verified_safe_no_remediation_required`.
8. **Record** the before/after sanitized outcomes.

**Uniqueness direction remains safe.** Insensitive → sensitive makes the unique index *more*
discriminating, so no new duplicate-key violations are possible. The behavioral change is that
lookups become case-sensitive; Peak's writers persist and compare these values verbatim, so no
reliance on case-insensitive matching is expected — confirm rather than assume. The **downgrade**
direction is the unsafe one and is a rollback of last resort.

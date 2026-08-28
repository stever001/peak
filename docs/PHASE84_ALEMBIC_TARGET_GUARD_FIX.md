# Phase 84 — Fixing the Alembic Lab/Production Target Guard

**Baseline:** `66c3bc0` — "Add Phase 83 peak-lab provisioning and verification". Branch `main`, clean
tree at baseline, repo Alembic head `014_engagement_classification`, 14 migrations, 18 tables, 12
writers, no standing production write enablement.

**Phase 84 is a Fix Now source-only safety defect fix.** It closes the seam Phase 83 §7.7 recorded as
the largest residual risk. **No production database and no lab database was contacted.** No
environment file was sourced, no connection was opened, no migration was run against any live target,
**no migration `015` was created**, no `peak_lab_scenario` was created, no writer was invoked, and no
record of any kind was created. Every URL this phase exercises is **synthetic**.

**No provider name, hostname, service URI, DSN, username beyond the credential names this repository
already tracks, password, token, certificate, price, environment value, or local secret path** appears
in any file this phase adds or edits.

---

## 1. The defect

`alembic/env.py` resolved its URL from `PEAK_DATABASE_URL` and nothing else. **No variable name says
which environment that URL points at**, so an intended lab migration, run in a shell that still held a
production value, would have migrated production — silently, and successfully. Phases 82 and 83 both
recorded the separation as **procedural only**: shell discipline, with nothing in source enforcing it.

**Why it had to be fixed before anything else.** The accident was survivable only because production
and the repository were both sitting at head `014` with nothing further to apply, which made a
misdirected `upgrade head` a no-op. That is an accident of timing, **not a control**, and Phase 83 §7.7
stated exactly when it expires: **the moment a migration `015` exists**. So the guard lands first, and
`015` waits.

---

## 2. What was added

| file | change |
| --- | --- |
| `alembic/migration_target_guard.py` | **new** — the guard, stdlib-only, ~200 lines |
| `alembic/env.py` | loads the guard by path and calls it on the resolved URL, in both modes |
| `tests/validate_phase84_alembic_target_guard.py` | **new** — the harness, synthetic URLs only |
| `Makefile` | `validate-phase84`, added to `make validate` |
| 12 existing harnesses | over-broad authoring-time scope guards corrected — 13 checks (§7) |
| docs | this file, plus concise updates to five existing documents |

**No migration file, model, table, writer, allowlist entry, schema, or enum was added or edited.**

---

## 3. The environment contract

| variable | value | required when |
| --- | --- | --- |
| `PEAK_ALEMBIC_TARGET` | `lab` \| `production` | **every** MySQL/MariaDB migration |
| `PEAK_LAB_MIGRATION_CONFIRM` | `1` | target is `lab` |
| `PEAK_PRODUCTION_MIGRATION_CONFIRM` | `1` | target is `production` |

`PEAK_DATABASE_URL` is unchanged and remains the one variable naming the migration URL. The guard adds
targeting; it does not add a second URL variable.

**Each confirmation accepts the exact string `1` and nothing else** — not `true`, not `yes`, not an
empty value — so a half-set variable fails closed. **The two confirmations do not substitute for each
other**: a production confirmation left standing in a shell does not satisfy the lab branch, and the
reverse is also refused.

**`PEAK_LAB_CONFIRM` is deliberately not used.** Phase 82 published it as *reserved and a no-op*, so an
operator may reasonably believe it is already set somewhere and inert. A guard must not share a name
with something documented as doing nothing.

---

## 4. Behaviour

**MySQL/MariaDB with no `PEAK_ALEMBIC_TARGET`, or an unsupported one, fails** — `staging`, `test`, and
a typo are all refused. Every check below runs **before the engine is created**, so a mis-aimed run
never reaches a connection.

### 4.1 `PEAK_ALEMBIC_TARGET=lab`

Passes only when **all** hold:

- `PEAK_LAB_MIGRATION_CONFIRM=1`
- the parsed database/schema is exactly **`peak_lab`**
- the parsed username is exactly **`peak_lab_migrate`**

Rejected, each with its own reason code: `defaultdb` and the MySQL system schemas
(`lab_schema_is_provider_default` — a lost or unwritten schema segment must never pass as the lab); any
production marker in the user or schema (`production_marker_under_lab_target`); any other schema
(`lab_schema_mismatch`); any other user, including `peak_lab_runtime`
(`lab_user_mismatch`); a missing confirmation (`lab_not_confirmed`).

### 4.2 `PEAK_ALEMBIC_TARGET=production`

Requires `PEAK_PRODUCTION_MIGRATION_CONFIRM=1`, and rejects **any lab marker** — schema `peak_lab` or
anything carrying `peak_lab`, user `peak_lab_migrate` or anything carrying `peak_lab`
(`lab_marker_under_production_target`) — as well as a provider default database and a URL naming no
schema or no user.

**Passing this branch is not authorization.** It means the URL is *consistent with* a production
migration, nothing more. **Production migrations remain unauthorized outside a separately approved
phase**, and this guard neither grants that approval nor stands in for it. It exists to stop the wrong
environment being migrated, never to bless the right one.

### 4.3 SQLite and every other dialect

**Bypassed entirely**, with no environment set at all. Only `mysql` and `mariadb` are guarded. Local
harnesses point at a temporary file, are disposable by construction, and are never an environment worth
confusing — the Phase 47 regression run (`alembic upgrade head` to 18 tables on a temp-file SQLite
database) passes unchanged, and Phase 84's own harness re-runs it with all three new variables
scrubbed from the process environment.

---

## 5. Value-free by construction

The guard **opens no file**, reads no `.env` or credential file, imports no database library or
driver, creates no engine or connection, issues no SQL, and opens no socket or subprocess. It parses
the URL textually and keeps **only two fields** — username and database — discarding host, port,
password, and query string rather than storing them.

Failure messages therefore carry **the target name, a classification of the parsed user and schema, a
reason code, and the expected constants** — never a password, host, port, query parameter, or whole
connection string. The harness asserts this by running every failing case in the decision table and
scanning each message for the synthetic password, host, port, query parameter, `://`, and the whole
DSN.

---

## 6. The lab migration invocation pattern

For a **future**, separately approved phase. Nothing here was run.

In a fresh shell that has never held a production value, with **exactly one** lab env file sourced —
the migration one, basename `peak-lab-migrate.env`, which lives outside the repository and sets
`PEAK_DATABASE_URL`:

```sh
export PEAK_ALEMBIC_TARGET=lab
export PEAK_LAB_MIGRATION_CONFIRM=1
python -m alembic upgrade head
```

The Phase 83 shell discipline still applies in full and is not replaced by the guard: no production
env ever sourced in that shell, one env file at a time, never `env` / `printenv` / `set` / `set -x`,
and the shell closed or the variables unset afterwards. The guard is a second, independent control —
**it now fails the run rather than trusting the operator got the shell right.**

**No Make target runs a migration.** A target that sources a secret file was rejected outright, and a
target that only re-exports the two variables would add a command whose whole purpose is to run
`alembic upgrade` against a live database — which nothing in this repository does today, and which
should stay a deliberate, typed command. The pattern is documented instead.

---

## 7. Thirteen scope-guard corrections across twelve harnesses, and why they were necessary

**`alembic/env.py` had been frozen by accident.** Phase 84 is the first phase since Phase 47 to change
it, and three separate classes of over-broad authoring-time scope guard blocked the change. None of
them was testing what its label claimed, and each would have blocked *any* later phase, not just this
one. All three are the failure mode Phase 49's own comments already describe — an authoring-time claim
about one phase's working tree, left ungated, becomes a permanent freeze on the repository.

1. **Eleven harnesses (Phases 57, 62–70, 72) diffed the whole `alembic/` directory under a label
   reading "no migration file was added or modified".** The pathspec is now `alembic/versions`, so each
   check tests exactly what it says. Nothing else about them changed, and each still fails if a
   migration file is touched.
2. **Phase 49 asserted *unconditionally* that `alembic/env.py` had no pending diff.** Its sibling scope
   checks were already gated on whether Phase 49 had landed; this one was missed. It is now gated with
   them, so it still constrains Phase 49's own tree and no longer freezes `env.py` forever.
3. **Phase 72's whole-tree scope guard diffed from Phase 72's baseline with no gate** — the
   thirteenth correction, and the second in that one file, so it judged
   every later phase's files against Phase 72's allowlist. It passed only because Phases 73–83 were
   docs-only, and `docs/` was excluded. It is now gated on whether Phase 72 has landed. Its
   substantive companion check — that no prior-phase operator utility was modified — stays
   unconditional and still passes.

**No harness lost a substantive assertion.** Phase 49's promises about `env.py` are still asserted
unconditionally from the file's *content*, not its diff: it still reads `PEAK_DATABASE_URL`, still
never references `PEAK_RUNTIME_DATABASE_URL` or `PEAK_PRODUCTION_DB_URL`, and the runtime helper still
fails closed. Phase 84 verified all of them.

---

## 8. Validation

Offline throughout. **`make validate` passes all 70 harnesses including the new
`validate-phase84` — 9,071 checks, 0 failures.** `make db-check` passes; `make mysql-parity-static`
reports 109 passed, 0 failures, 0 warnings; `make mysql-collation-audit` reports 309 columns audited,
212 governed, **0 unpinned**, status unchanged at `MODEL_POLICY_SATISFIED_PRODUCTION_UNVERIFIED`; and
`make writer-enablement-decision-gate` passes still reporting
**`safe_to_write_production_now=false`**. Read-only `alembic heads` reports
`014_engagement_classification` and `alembic history --verbose` shows the same **14** revisions,
`001_initial` through `014`. The runtime connectivity gate `--self-test` passes on both interpreters
with `production_connectivity_result=not_tested` and `self_test_mode_no_database_contacted`.

**Phase 47 passes unchanged**, including its live SQLite `upgrade head` / `downgrade` / re-`upgrade`
regression through the new guarded accessor.

---

## 9. Non-claims and boundaries

- **No production access and no lab access.** No env file sourced, no connection opened, no verifier
  run against any environment, no service/network/configuration changed anywhere.
- **No migration executed** — no `upgrade`, `downgrade`, or `stamp` against any live target. The only
  migrations run were against throwaway temporary SQLite files inside the harnesses.
- **No migration `015`**, and no change to the application schema.
- **No `peak_lab_scenario`**, no scenario table, and **no measured row**.
- **No writer was invoked and no record was created** — no Client, Engagement, intake note, source
  ingestion, evidence reference, review record, review bundle, report draft, capsule, client-facing
  output, or AgentNet publication record.
- **No cloud, provider, API, or console contact.**
- **No dependency installed** — the guard is stdlib-only.
- **No secret, DSN, host, provider name, environment value, or local secret path committed.** Every
  URL in the guard and the harness is synthetic, pointing at a non-resolvable placeholder host with a
  placeholder password that is a credential for nothing.
- **The guard authorizes nothing.** The Phase 51 writer-enablement decision gate remains the authority
  on writes, is environment-blind, and still reports `safe_to_write_production_now=false`.

---

## 10. Posture after Phase 84

- Repo head stays `014_engagement_classification`, **14 migrations, 18 tables, 12 writers**, and **no
  standing production write enablement**.
- **Alembic now requires explicit target and confirmation for MySQL migration execution.** Lab
  migrations must target `peak_lab` as `peak_lab_migrate` with explicit lab confirmation; production
  migrations require their own separate confirmation and remain unauthorized except in a separately
  approved phase.
- **SQLite and local test paths remain supported**, unchanged and unconfigured.
- Phase 83 §7.7 is **closed**. The remaining Phase 83 §7 items — unverified server-version parity,
  verifier and gate output that says "production" when pointed at the lab, the inert
  `mysql-parity-staging` target, and the stale 211/308 figure in
  `GOVERNED_MYSQL_COLLATION_POLICY.md` — are **all still open**, and none is addressed here.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** The reviewed
  Phase 79 source remains source-only, not evidence. **R1 remains provisional**, and the location
  finding stays **data-readiness and reliability only, never inventory accuracy.** The **R5 WMS scope
  clarification remains a reviewed scope-blocker enumeration only** and the **Phase 64 R5 export
  remains uncollected**. **R3–R7 remain deferred.** The Phase 74 outline is unmodified and `fnd_000`
  remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

---

## 11. Sequencing

**This fix must be committed and accepted before any migration `015` or any further lab migration
work.** The scenario-seeding phase Phase 83 §10 described as "Phase 84" is therefore **renumbered to
Phase 85**, which may proceed to `peak_lab_scenario` planning and seeding — under its own separate
approval — only after this fix is committed and accepted.

---

## 12. Warnings and decisions needing review

1. **The guard checks the URL, not the server.** It proves the DSN *says* `peak_lab` /
   `peak_lab_migrate`; it does not prove the host behind it is the lab service. A production service
   holding a schema named `peak_lab` would pass. Nothing suggests one does, and the Phase 83 shell
   discipline still covers the host — but this is a name check, and it should be read as one.
2. **The production branch is intentionally weaker than the lab branch**, because production's schema
   and user names are not recorded in this repository and must not be. It requires a confirmation and
   excludes lab markers; it cannot require an exact name the way the lab branch does.
3. **`PEAK_ALEMBIC_TARGET` is new and nothing else reads it.** The connectivity gate and the collation
   verifier still take a lab DSN in a production-named variable with no target of their own. Extending
   the same targeting to those two tools is a separate, source-only decision, deliberately not taken
   here.
4. **Renumbering.** Phase 83 §10's "Phase 84" is this repository's **Phase 85**. Anyone reading Phase
   83 alone will expect scenario seeding under this number.

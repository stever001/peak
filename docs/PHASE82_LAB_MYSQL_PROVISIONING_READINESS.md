# Phase 82 — Lab MySQL Provisioning Readiness

**Baseline:** `9bd9d15` — "Add Phase 81 production-parity lab MySQL plan". Branch `main`, clean tree
at baseline, Alembic head `014_engagement_classification`, 14 migrations, 18 tables, 12 writers, and
**no standing production write enablement**.

**Phase 82 is readiness/runbook only.** No production access occurred. **No cloud service, API, or
console was contacted.** No database, service, schema, user, or credential was created. No migration
was run. No writer was invoked and no record of any kind was created. No new infrastructure was
added — no migration, model, writer, allowlist pair, schema, table, operator, or harness. **No
environment file was created or sourced and no connection was opened**; the runtime connectivity gate
was run in `--self-test` mode only. Head stays `014_engagement_classification` with 14 migrations, 18
tables, and 12 writers, and **production remains untouched**.

This phase writes the runbook Phase 83 executes. **Phase 82 does not execute it.**

**Phase 83 requires explicit user approval**, because it creates **recurring-cost managed
infrastructure**. Nothing in this document constitutes that approval, and approval must not be
inferred from the existence of the runbook.

---

## 0. Phase renumbering, and what it supersedes

Phase 81 wrote its plan against a numbering in which **provisioning was Phase 82**. A readiness phase
was inserted, so every step Phase 81 assigned to "Phase 82" is now **Phase 83**, and everything it
assigned to "Phase 83" is now **Phase 84**. Phase 81's text is unchanged in substance; only the phase
labels shift. Where this document and Phase 81 disagree on a number, **this document is current**.

Two naming decisions in this document also supersede Phase 81:

| Phase 81 said | Phase 82 says | why |
| --- | --- | --- |
| read-only lab user `peak_lab_readonly` | **`peak_lab_verify_ro`** | the role is *verification*, and `_ro` states the posture in the name an operator types |
| operative env vars `PEAK_LAB_MIGRATION_URL` / `PEAK_LAB_RUNTIME_URL` / `PEAK_LAB_READONLY_URL` | **retired as operative names** — see §3 | **no tool reads them.** Each tool reads a fixed, production-named variable and nothing else. A `PEAK_LAB_*` variable that no tool reads is a false sense of separation, which is worse than none |

---

## 1. Resource naming

| thing | name |
| --- | --- |
| managed service label | **`peak_lab`** |
| controlled schema/database (Alembic-managed) | **`peak_lab`** |
| scenario schema/database (never Alembic-managed) | **`peak_lab_scenario`** |

**Explicitly:**

- **Not production.** A separate managed service with its own host, admin plane, connection endpoint,
  and credential namespace.
- **Not staging.** `PEAK_MANAGED_MYSQL_STAGING_DSN`, `make mysql-parity-staging`, and
  `PEAK_MANAGED_MYSQL_DISPOSABLE` already define "staging" as an **empty, disposable schema holding
  no data ever** — the parity gate *refuses* a DSN not marked disposable. The lab is durable by
  design. Reusing the word would let someone later point the staging variable at the lab and silently
  void the disposability contract.
- **Not a second database inside the production service.** Rejected in Phase 81 §2: same host, same
  admin plane, same endpoint and connection limits, so one mistyped DSN reaches production — which
  holds real `internal_test` records that runtime **cannot delete**.
- **Not the `--env test` environment.** `test` collides with the `internal_test` engagement
  classification, a different axis entirely.

`peak_lab`, `peak_lab_scenario`, and the `PEAK_LAB_*` namespace have **zero collisions** in the
repository today.

**Provider stays out of the repository.** The repo names no cloud vendor and this document adds none.
Provider and version family are recorded out-of-band. The lab should match production's MySQL
**version family**, since matching production is the entire point.

---

## 2. Credential plan — names and posture only, no values

Three lab users, three privilege sets, **never interchangeable and never pointed at the same database
user**. Names only below; **no secret value appears in this repository, in any phase.**

| role | lab user | privileges | mirrors the production role read by |
| --- | --- | --- | --- |
| migration | **`peak_lab_migrate`** | DDL on `peak_lab` only — enough to apply the existing 14 Alembic migrations, and no more | `PEAK_DATABASE_URL` |
| runtime | **`peak_lab_runtime`** | **exactly `SELECT` + `INSERT`** on `peak_lab` | `PEAK_RUNTIME_DATABASE_URL` |
| read-only verifier | **`peak_lab_verify_ro`** | **`SELECT` only** | `PEAK_PRODUCTION_DB_URL` |

**Posture, stated as constraints:**

- **No production credential is reused**, in either direction. No lab value is ever written into a
  production env file, and no production value into a lab one.
- **No broad grants.** Each user is scoped to the schema it needs. `peak_lab_scenario` is **not**
  granted to `peak_lab_runtime` or `peak_lab_verify_ro` in Phase 83, because Phase 83 does not create
  that schema.
- **No `GRANT OPTION`** on any lab user.
- **No global privileges.** `USAGE` at `*.*` is the only acceptable global grant — the connectivity
  gate treats it as `HARMLESS_GLOBAL` and everything else at `*.*` as excess.
- **No `UPDATE` and no `DELETE` for runtime**, unless separately justified and approved. This is not
  a formality: the Phase 50 gate's `REQUIRED_GRANTS = ("SELECT", "INSERT")` and its 27-entry
  `FORBIDDEN_GRANTS` list are **fixed in source**, so a lab runtime user carrying `DELETE` for
  convenience **fails the gate**. Provisioning to the production posture keeps the gate reusable
  unmodified and preserves what a pass means.
- **The audit consequence carries over intact.** A lab runtime process cannot rewrite or remove what
  it wrote, so **lab records are durable by construction** and must be designed that way rather than
  written and cleaned up. Reset and teardown are **migration-credential** operations, deliberately
  and separately — never runtime.
- **No credential of any kind for AgentNet publication, capsule publication, final report, or
  client-facing output.** The lab carries no such authority, and the AgentNet resolver gate stays
  **shut rather than relaxed**, precisely because the public resolver is live.

---

## 3. Environment file names, outside the repository

**Names only. Phase 82 creates none of these files.** They are created in Phase 83, outside the
repository, and no value from them ever enters Git or any log.

| file | the one variable it sets | read by |
| --- | --- | --- |
| `peak-lab-migrate.env` | `PEAK_DATABASE_URL` → the `peak_lab_migrate` DSN | `alembic/env.py` |
| `peak-lab-runtime.env` | `PEAK_RUNTIME_DATABASE_URL` → the `peak_lab_runtime` DSN | `tools/production_runtime_connectivity_gate.py` |
| `peak-lab-ro.env` | `PEAK_PRODUCTION_DB_URL` → the `peak_lab_verify_ro` DSN, **plus** `PEAK_PRODUCTION_DB_READONLY_CONFIRM=1` | `tools/production_mysql_collation_verify.py` |

**File names, not paths — deliberately.** The three files live in the **operator credential
directory outside the repository**, the same out-of-repo location the production env files use. That
directory is **named nowhere in this repository, by standing convention**: seven validation harnesses
(Phases 47, 49, 50, 51, 53, 54, 55, 57) fail if a tracked file names it or names an operator
credential file, so `make validate` enforces the rule mechanically. Basenames identify the files
without disclosing where credentials live; the operator already knows the directory.

**Why the variables carry production names.** This is the central operational fact of the whole
runbook, and it is wider than Phase 81 recorded. Phase 81 flagged the seam for Alembic alone; reading
the tools shows **all three roles have it**:

- `alembic/env.py` `_get_url()` reads **only** `PEAK_DATABASE_URL`. No `-x`, no `--name`, no section
  switching, no fallback.
- The connectivity gate reads **only** `PEAK_RUNTIME_DATABASE_URL` (`RUNTIME_URL_ENV`) and fails
  closed with exit 2 if it is absent — there is no fallback variable by design.
- The collation verifier reads `PEAK_PRODUCTION_DB_URL` then `PEAK_DATABASE_URL`
  (`PRODUCTION_DSN_VARS`), and **refuses with exit 2** if a DSN is present without
  `PEAK_PRODUCTION_DB_READONLY_CONFIRM` set to an affirmative value.

So there is no variable name that says "lab". **The variable name cannot tell you which environment
it points at — only the shell discipline in §4 can.** That is why §4 is mandatory rather than
advisory, and why it applies to all three files, not just the migrate one.

**`PEAK_LAB_*` names are documentation labels, not operative variables.** Each file may carry a
comment naming its role; it must not rely on a `PEAK_LAB_*` variable to do anything, because nothing
reads one.

**`PEAK_LAB_CONFIRM=1` is reserved, and is a no-op today.** **No script in the repository reads it**
as of this baseline. Phase 83 may set it as a human marker, and must not treat it as a guard. Making
it load-bearing would require a source change, which is not authorized here.

**Secrets never enter the repository.** `.env` and `.env.*` are gitignored; only `.env.example`
(placeholders) is tracked. Every gate must continue to report `secrets_printed=false`, and failures
continue to be reported by exception **type** only, because driver messages routinely embed the
connection string.

---

## 4. The lab-only shell guard — mandatory for Phase 83

**Required, because every lab DSN is placed in a production-named variable (§3).** This is manual
shell discipline, not a script; making it a script is a source change that is not authorized here.

**Before:**

1. **Open a fresh shell.** Never reuse a shell that has held a production value at any point.
2. **Source no production env file in that shell**, for any reason, before or after.
3. **Source exactly one lab env file at a time.** Never two. Never a lab file and a production file.
4. **Verify prompt and working context** before any command that connects.

**During:**

5. **Never print the environment.** No `env`, no `printenv`, no `set`, no `export -p`, no `echo
   $PEAK_...`, no `declare -p`. Not for debugging, not once.
6. **Never `set -x`.** Tracing echoes the DSN into the terminal and into any capture of it.
7. **Before `alembic upgrade`, assert the target is the lab** — host/service/user must indicate
   `peak_lab`. Assert it by reading the sourced file at the path you intended to source, not by
   echoing the variable.
8. **Stop immediately if any variable, path, hostname, service label, or username mentions the
   production service or a production user.** Stop, close the shell, and start over. Do not "fix it
   in place" — a shell that has held a production value is disqualified for the rest of the phase.

**After:**

9. **Close the shell**, or `unset` every variable the file set, before doing anything else.
10. **Do not paste command output containing a DSN anywhere** — not into a doc, a commit, an issue,
    or a chat.

**One mitigation, and its expiry date.** Production is already at head `014`, so a misdirected
`alembic upgrade head` is currently a **no-op**. This is a mitigating accident, **not a control**, and
it **stops being true the moment a `015` exists** — which is one more reason no `015` is authored
while this seam stands.

**One genuine control, worth knowing.** The connectivity gate scrubs `PEAK_DATABASE_URL`,
`PEAK_PRODUCTION_DB_URL`, and `PEAK_PRODUCTION_DB_READONLY_CONFIRM` from its own process environment
before anything else runs, so it *cannot* silently fall back to a migration or production variable. It
is the one tool in the set that enforces separation in code rather than by discipline.

---

## 5. Migration plan for Phase 83

- **Apply the existing 14 migrations to `peak_lab` only**, from an **empty** schema.
- **Target head `014_engagement_classification`.** Nothing beyond it.
- **Expected result: 18 controlled tables plus `alembic_version`.**
- **Create no migration `015`.** Not in Phase 82, not in Phase 83. The lab must never become the
  route by which an untested `015` reaches production.
- **Do not alter production.** No migration, `alembic stamp`, `UPDATE`, `DELETE`, manual SQL, or
  cleanup is issued against production at any step.
- **Create no measured scenario rows.** `peak_lab_scenario` is **not created in Phase 83**.
- **Invoke no writer and create no Peak record**, in the lab or anywhere else.
- Parity target: `InnoDB` + `utf8mb4`, with **`utf8mb4_bin` pinned per-column on governed columns** —
  identity, scope, idempotency keys, and fingerprints. MySQL 8's `utf8mb4` default is
  case-insensitive, so determinism comes from per-column pinning only, exactly as in production. This
  is what the `UNIQUE (owner_id, client_id, engagement_id, idempotency_key)` boundary depends on
  across 11 tables.
- `alembic/env.py` runs the Phase 47 `alembic_version` widening preflight automatically in online
  mode, so a fresh lab bootstrap does **not** hit the Phase 46 `VARCHAR(32)` failure at migration
  `008`. Rehearsing that path against a throwaway container remains **optional**; if used, every
  container artifact stays **outside the repository**, since
  `tests/validate_phase49_runtime_database_url_separation.py` asserts `docker-compose.yml`,
  `Procfile`, `deploy.yaml`, and `runtime.env` do **not** exist at repo root.

---

## 6. Verification plan for Phase 83

Run under the §4 guard, one env file at a time.

**A. Schema state — via `peak-lab-ro.env` (`peak_lab_verify_ro`):**

1. **Alembic head check** — head is exactly `014_engagement_classification`.
2. **Table count check** — **18** base tables, plus `alembic_version`.
3. **Migration count check** — **14** applied revisions.
4. **Collation / governed-column check** — engine `InnoDB`, charset `utf8mb4`, `utf8mb4_bin` on every
   governed column. `tools/production_mysql_collation_verify.py` already pins
   `EXPECTED_ALEMBIC_HEAD = "014_engagement_classification"` and `EXPECTED_TABLE_COUNT = 18`, so it
   verifies the lab **unmodified**.

**B. Grants — one check per lab credential:**

5. `peak_lab_migrate` — DDL on `peak_lab` only; **no `GRANT OPTION`**, no global privileges beyond
   `USAGE`.
6. `peak_lab_runtime` — **`SELECT` + `INSERT` only**; **no `UPDATE`, no `DELETE`**, no DDL, no
   `GRANT OPTION`, no global privileges beyond `USAGE`. Verify by running the connectivity gate live
   under `peak-lab-runtime.env`: expect `required_grants_present=true` and
   `excess_grants_present=false`.
7. `peak_lab_verify_ro` — **`SELECT` only**; **cannot write**. Confirm from its grant list, not by
   attempting a write.

**C. Environment shape:**

8. **`peak_lab` exists** and is the Alembic-managed controlled schema.
9. **`peak_lab_scenario` does not exist yet** — Phase 83 does not create it. (Phase 81 §7 describes
   it as a later, separately approved step; the go/no-go in §8 covers only the controlled schema.)
10. **No measured rows anywhere.** No Peak record, no scenario row. Confirm the controlled tables are
    empty apart from `alembic_version`.
11. **Production remains untouched** — no production verifier run, no production connection, no
    production credential used, and no production env file sourced at any point in the phase.

**D. Repo state, offline, after the fact:**

12. `make validate`, `make db-check`, `make mysql-parity-static`, `make mysql-collation-audit`, and
    `make writer-enablement-decision-gate` all still pass, and the decision gate still reports
    `safe_to_write_production_now=false`.

**Note on check 9 vs. §1.** `peak_lab_scenario` is *named and reserved* in Phase 82 so nothing else
claims the name; it is *created* only in a later, separately approved phase. Reserving a name and
creating a schema are different acts, and only the first happens before approval.

---

## 7. Tooling gap notes — known, and deliberately not fixed here

**Do not fix any of these in Phase 82.** Phase 83 uses the existing tools with careful lab env
discipline. A later **source-only** phase may add lab-specific wrappers **after the lab exists, and
only if the need is demonstrated** — building a wrapper for an environment that does not exist yet is
speculative work against an unverified target.

1. **`make mysql-parity-staging` is not a live verifier today.** `run_staging()` accepts the DSN and
   the disposable marker, then emits `[hold]` and returns 0 **without connecting** — the live parity
   run was never implemented. Phase 83 must therefore verify with
   `tools/production_mysql_collation_verify.py` under the lab read-only credential, which works
   unmodified. Implementing the live parity path is a separate, later decision.
2. **`make mysql-parity-staging` reads `PEAK_MANAGED_MYSQL_TEST_DSN`, not the staging one.** The
   recipe passes no `--env`, and `--env` defaults to `test`. Worth knowing before anyone assumes the
   staging variable is wired.
3. **`production_mysql_collation_verify.py` can verify the lab, but its output says "production".**
   Pointed at a lab read-only DSN it reports `production_connection_made`,
   `production_connectivity_result`, and messages of the form "production alembic head does not
   match…". **Cosmetic today; misleading if a lab run's output ever becomes an audit artifact.** Any
   Phase 83 record of such a run must state in the surrounding text which environment was read, since
   the output itself will not.
4. **The verifier's affirmation variable is also production-named.** Enabling a lab read means setting
   `PEAK_PRODUCTION_DB_READONLY_CONFIRM=1` — affirming "a read-only inspection of production" while
   pointed at the lab. Same class of problem as (3), same resolution: the §4 guard and explicit
   surrounding documentation.
5. **`alembic/env.py` has no separate lab target** — only `PEAK_DATABASE_URL`, with no `-x`, no
   `--name`, and no section switching. **This remains the largest residual risk in the plan.** A
   lab-aware target resolver is a candidate for a later phase and needs its own approval.
6. **Adding `--env lab` to the managed-MySQL tools** would touch `choices` and `ENV_DSN_VARS` in two
   files. Phase 83 does not need it — the read-only verifier and the connectivity gate reach the lab
   by role variable alone. Deferred.
7. **The writer-enablement decision gate is environment-blind.** It hardcodes every authorization to
   `false` and contacts no database. Authorizing a lab write is therefore a **deliberate source edit
   with its own review** — it cannot and must not be flipped by an environment variable. This belongs
   to a later phase, not Phase 83.
8. **Documentation currency: governed-column counts.** `GOVERNED_MYSQL_COLLATION_POLICY.md` and
   migration `013` state **211 governed columns of 308**; `make mysql-collation-audit` now reports
   **212 of 309**. The difference is migration `014`'s `engagement_category`, correctly pinned
   `utf8mb4_bin` on MySQL. **Not a defect** — the Phase 42/44 figures simply predate `014` and read as
   current. Annotated here; not corrected here.

---

## 8. Phase 83 go/no-go checklist

**Phase 83 may proceed only if the user explicitly approves every line below.** Approval must be
explicit and must not be inferred from a phase prompt, from this document, or from Phase 81.

- [ ] **Recurring managed MySQL cost.** A separate managed service is the only recommended option
      carrying a recurring bill. It is a deliberate trade for blast-radius isolation, and it is the
      user's call.
- [ ] **Cloud provisioning** — contacting a provider console or API at all.
- [ ] **Lab service creation** — creating the managed service labelled `peak_lab`.
- [ ] **Lab schema, user, and credential creation** — the `peak_lab` database and the three users
      `peak_lab_migrate`, `peak_lab_runtime`, `peak_lab_verify_ro`.
- [ ] **Applying the existing 14 migrations to the lab**, to head `014_engagement_classification`.

**Not in scope for Phase 83 even with the above approved**, and each requiring its own separate
approval later:

- creating `peak_lab_scenario` or any measured scenario row;
- invoking any writer, in any environment;
- creating the lab engagement anchor or any Peak record;
- authoring migration `015`;
- granting the lab runtime credential `UPDATE` or `DELETE`;
- any client-facing report, final report, capsule publication, or AgentNet resolver publication
  authority;
- any source change to the tools listed in §7.

---

## 9. Non-claims and boundaries for Phase 82 itself

- **No production access of any kind.** No env file was sourced, no connection opened, no cloud
  console or API contacted, no production verifier run. The runtime connectivity gate was run in
  `--self-test` mode only, reporting `self_test_mode_no_database_contacted`.
- **No cloud service, API, or console was contacted** — no provider was reached, named, or selected.
- **No database, service, schema, user, or credential was created**, in any environment.
- **No environment file was created.** The names in §3 are names in a document; the files do not
  exist.
- **No migration was run**, and no `alembic stamp`, `UPDATE`, `DELETE`, manual SQL, or cleanup was
  issued. No application table was scanned, counted, or probed.
- **No writer was invoked and no record was created** — no production row, no lab row, no
  `review_records`, source ingestion, evidence reference, review bundle, report draft, Client,
  Engagement, intake note, capsule, client-facing output, or AgentNet publication record.
- **No new infrastructure** — no migration, model, writer, allowlist pair, schema, table, operator, or
  harness. **Docs only.**
- **No branch, worktree, or commit** was created by this phase's work.
- **No artifact body, fixture, example, or sample packet** was read, printed, committed, or stored.
- **No secrets or environment values** were printed or committed. No DSN, host, username, password,
  or token appears anywhere in this document.
- **No real client data.** `internal_test` only.
- **This runbook authorizes nothing.** It describes what Phase 83 would do; Phase 83 requires its own
  explicit approval.

---

## 10. Posture after Phase 82

- **Nothing in the database changed.** Head stays `014_engagement_classification`, 14 migrations, 18
  tables, 12 writers, and **no standing production write enablement**.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** The Phase 80
  closure stands exactly as recorded — scenario-specific, not a refutation, not a state change, and
  no R8 row was modified.
- **The reviewed Phase 79 source remains source-only, not evidence.**
- **R1 remains provisional**, and the location finding stays **data-readiness and reliability only,
  never inventory accuracy.**
- **The R5 WMS scope clarification remains a reviewed scope-blocker enumeration only**; R5 WMS scope
  itself remains unresolved, and the **Phase 64 R5 receiving/putaway export remains uncollected.**
- **R3–R7 remain deferred**, with the count/variance request **conditionally required /
  scope-dependent.**
- **The Phase 74 outline is unmodified** and `fnd_000` remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

---

## 11. Warnings and decisions needing review

1. **Phase renumbering (§0).** Phase 81's "Phase 82" is this document's **Phase 83**. Phase 81's text
   was not rewritten; the mapping is recorded here instead. Worth knowing when reading the two
   documents side by side.
2. **Every lab DSN sits in a production-named variable (§3), for all three roles** — not just for
   Alembic, as Phase 81 recorded. There is no variable name that says "lab", so **the §4 shell guard
   is the only separation control** for the migrate and read-only roles. The connectivity gate is the
   sole exception: it scrubs the production variables in code.
3. **`PEAK_LAB_CONFIRM` is a no-op.** No script reads it, and **Phase 84 deliberately did not adopt
   it**: a guard must not share a name with something this document published as reserved and inert.
   Phase 84's real variables are `PEAK_ALEMBIC_TARGET` plus `PEAK_LAB_MIGRATION_CONFIRM` /
   `PEAK_PRODUCTION_MIGRATION_CONFIRM`, and `alembic/env.py` now refuses a MySQL migration that
   declares no target or whose URL does not match the declared one, **before any engine is created**.
   That closes the §7 seam this document recorded, in source rather than by procedure — the shell
   discipline above still applies in full alongside it. **Phase 84 contacted no database, ran no
   migration against any live target, created no `015`, invoked no writer, and created no record.**
   See [`PHASE84_ALEMBIC_TARGET_GUARD_FIX.md`](PHASE84_ALEMBIC_TARGET_GUARD_FIX.md). The name below
   must not be relied on as a guard unless
   a later, separately approved source change makes it load-bearing.
4. **Env-file *paths* are deliberately absent from every tracked file (§3).** Only basenames appear,
   because the repo's hygiene harnesses ban naming the operator credential directory. If a future
   phase wants the full path recorded, that is a harness change with its own review — not a doc edit.
5. **`PEAK_LAB_*_URL` retired as operative names.** Phase 81 named them; nothing reads them. Retained
   only as documentation labels, so that no one mistakes them for a control.
6. **The read-only verifier's output labels say "production" when pointed at the lab (§7.3/§7.4)**,
   and enabling it requires setting a variable named `PEAK_PRODUCTION_DB_READONLY_CONFIRM`. Any lab
   run recorded as evidence must be captioned with the environment it actually read.
7. **Governed-column counts are stale in `GOVERNED_MYSQL_COLLATION_POLICY.md` (211/308 vs. the
   audit's 212/309, §7.8).** Not a defect; annotated, not corrected.
8. **Cost.** The recurring managed-service bill is the single decision that most needs an explicit
   answer before Phase 83, and it is the user's call alone.
9. **`docker-compose.yml` at repo root fails `make validate`.** Any optional container rehearsal must
   keep every artifact outside the repository.

---

## 12. Corrected by Phase 83 — read this first

Phase 83 executed this runbook. See
[`PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md`](PHASE83_PEAK_LAB_PROVISIONING_AND_VERIFICATION.md),
which is current where the two disagree. Three corrections:

1. **The managed service label is `peak-lab`, not `peak_lab`.** §1 of this document specifies a
   service label the provider cannot accept — **its service names disallow underscores.** This was a
   defect in the runbook, discovered at provisioning time. **Only the service label changes:** the
   controlled schema is still **`peak_lab`** and the credentials are still `peak_lab_migrate`,
   `peak_lab_runtime`, `peak_lab_verify_ro`, because those are created through SQL, where MySQL's
   identifier rules apply rather than the provider's. The schema was created by `CREATE DATABASE`
   from an admin session rather than the provider console, so the hyphenated label could not become a
   schema name by accident. The isolation posture is unaffected — `peak-lab` is plainly neither
   production nor staging.
2. **The `peak_lab_scenario` reservation held.** §6 check 9 required that it not exist after
   Phase 83, and verification confirmed it does not.
3. **§4's shell guard was applied and proved necessary, but was not sufficient on its own.** The guard
   governs commands; it does not govern **file authoring**, and that is where the one incident
   occurred. A DSN written **unquoted** into a lab env file caused the shell to fail glob expansion on
   the `?` in its query string and **echo the line, including the migration credential's password**,
   before any guard check could run. **`peak_lab_migrate` was rotated** and the exposed value was
   never used again. **Add to the guard, for any future environment file:** every value is
   **single-quoted**, and files are produced by an out-of-repo generator with hidden password input
   and URL-encoding rather than hand-edited. Hand-editing produced five distinct DSN defects across
   three attempts — missing `KEY=` prefix, missing `@`, hyphenated schema name, relative certificate
   path, and the unquoted value that caused the exposure.

**The fourth, temporary admin env file contemplated in §3 was never created** — the administrative SQL
ran in an operator session instead, so that deviation did not occur.

**§7's tooling-gap notes all held.** The verifier worked against the lab unmodified and printed
production-named output exactly as predicted (§7.3/§7.4), requiring the captions Phase 83 supplies;
`make mysql-parity-staging` was neither used nor fixed; and the governed-column count in
`GOVERNED_MYSQL_COLLATION_POLICY.md` remains stale at 211/308 against a verified **212**.

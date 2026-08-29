# Phase 85 — Creating and Seeding the peak_lab_scenario Source-System Schema

**Baseline:** `3892693` — "Add Alembic target guard for lab migrations". Branch `main`, clean tree at
baseline, repo Alembic head `014_engagement_classification`, 14 migrations, 18 controlled tables, 12
writers, no standing production write enablement.

**Phase 85 created and seeded `peak_lab_scenario` on the lab service only.** It is a **separate,
lab-only simulated source-system schema** holding internal synthetic measured data for future Peak
evidence and extraction work.

**`peak_lab_scenario` is not Alembic-managed**, carries **no `alembic_version` table**, holds **no
Peak controlled table**, and **is never production**. **No migration `015` was created**, **no live
Alembic migration ran**, **no write occurred to any `peak_lab` controlled table**, **no Peak writer
was invoked**, and **no Peak record of any kind was created**. **No production database, service,
project, schema, credential, or console was accessed or changed.**

**Scenario row bodies are not committed.** This document carries only the schema and table summary,
row counts, control totals, the content hash, credential posture, and safety posture. **No secret,
DSN, host, port, service URI, provider name, price, certificate path, environment value, or local
secret path appears in any file this phase adds or edits.**

---

## 1. The distinction that governs this phase

| schema | what it is | Alembic | production |
| --- | --- | --- | --- |
| `peak_lab` | the **controlled** Peak lab schema — 18 governed tables plus `alembic_version` | **managed** | never |
| `peak_lab_scenario` | a **simulated source-system** schema — synthetic measured input data | **never managed** | never |

These are different kinds of object and must not be conflated. `peak_lab` holds Peak's own governed
records under migration control. `peak_lab_scenario` holds **imitation upstream system data** of the
kind a client's WMS or ERP would expose — it is an *input* to future measurement, never a Peak record,
and nothing in it is evidence.

---

## 2. What was created

**Schema `peak_lab_scenario`** — `utf8mb4` / `utf8mb4_0900_ai_ci`, verified on the server. It already
existed at phase start, empty, with both properties already correct; the phase therefore **adopted it
after verifying its properties** rather than recreating it. Had either property differed, the phase
was written to stop.

**Eight tables**, all `InnoDB`, all `utf8mb4_0900_ai_ci`, with **37 identity and code columns pinned to
`utf8mb4_bin`** so joins and control totals are deterministic — the same per-column pinning discipline
the controlled schema uses, applied here for the same reason.

| table | purpose | rows |
| --- | --- | ---: |
| `scenario_runs` | one row per scenario version; carries the not-production and not-Alembic-managed flags | 1 |
| `source_systems` | the simulated upstream systems and their declared extract capability | 4 |
| `r8_system_record_map` | which system claims authority for which record domain, and whether it is settled | 10 |
| `r2_item_master` | item master attributes, complete and incomplete | 10 |
| `r9_location_bin_model` | location/bin structure, complete and partial and absent | 16 |
| `r1_inventory_snapshot` | on-hand rows with resolvable and unresolved locations | 32 |
| `r5_receiving_putaway_events` | receipt and putaway events with complete and incomplete timing | 14 |
| `scenario_control_totals` | stored counts, sums and the dataset content hash | 33 |

**87 data rows plus 33 control-total rows — 120 rows in total.**

Every table carries `scenario_id` and `scenario_version`, every data table carries a capture
timestamp, and every table has a primary key including the scenario identity, so **a duplicate seed
row cannot be inserted**.

---

## 3. The seeded scenario

**`internal_test_inventory_ops_v1`**, version `v1`, classification `internal_synthetic_lab`, origin
`synthetic_generated_internal`, flagged `is_production=0` and `alembic_managed=0` **in the data
itself**, not only in documentation.

**The dataset is deliberately mixed.** A scenario in which everything is clean cannot demonstrate that
a future readiness check works, so each dimension carries populations that should pass and populations
that should fail:

- **item master** — complete, incomplete, and ambiguous attribute sets, including a unit-of-measure
  conflict and an invalid case quantity
- **location model** — complete aisle/bay/level/bin structure, partial structure, and absent structure
- **inventory** — resolvable locations, locations naming a code absent from the location model,
  rows with no location at all, rows with no quantity, and rows with no unit of measure
- **receiving and putaway** — complete movement timing, missing timing, missing destination, a
  destination absent from the location model, and one event whose putaway precedes its receipt
- **system-record map** — authority resolved for some domains, contested for others, and wholly
  unresolved for the rest

**Every identifier is an obvious internal synthetic token** — `INTERNAL_SKU_001`, `INTERNAL_LOC_A01`,
`INTERNAL_RECEIPT_001`, `INTERNAL_SOURCE_WMS`, `INTERNAL_SOURCE_ERP` — and 90 identifiers were checked
against that pattern before anything was inserted. **No client name, customer name, vendor name,
brand, product name, address, or personal datum appears anywhere in the dataset**, and no
pseudo-client stands in for one. Item descriptions are explicitly synthetic by construction.

---

## 4. Control totals and content hash

**Dataset content hash (SHA-256, canonical serialisation of the seven data tables):**

```
18459dc1964bc5622d7c7b40ba88b4b2ed7fbc268bf65e20e66f22c828bea1cb
```

The hash was computed from the definition **before** the seed ran, recomputed from the rows **read
back out of the database** afterwards, and compared against the copy **stored in
`scenario_control_totals`**. All three agree.

| control | value |
| --- | ---: |
| data rows, all seven tables | 87 |
| item master — complete / incomplete / ambiguous | 5 / 3 / 2 |
| location model — complete / partial / absent | 9 / 3 / 4 |
| inventory — complete / incomplete / ambiguous | 20 / 10 / 2 |
| inventory — location resolvable / unresolvable | 25 / 7 |
| inventory — quantity present / absent | 29 / 3 |
| inventory — on-hand quantity sum | 2201.000 |
| receiving and putaway — timing complete / incomplete / ambiguous | 11 / 2 / 1 |
| receiving and putaway — location complete / incomplete / ambiguous | 11 / 2 / 1 |
| receiving and putaway — quantity sum | 2130.000 |
| system-record map — resolved / contested / unresolved | 4 / 3 / 3 |

**Seven of these totals were independently recomputed by aggregating the rows in SQL** rather than
read from the stored control table, and agreed. Two referential checks were also measured in the
database: no row claiming a resolvable location is in fact unresolvable, and every inventory row
resolves to an item-master row.

---

## 5. Re-run behaviour, and the correction policy

The applier has exactly three outcomes and **no fourth**:

1. **absent** → insert the scenario
2. **present and identical** → `idempotent_replay_no_rewrite`, nothing written
3. **present and different** → **stop**, reporting that a new scenario version slug is required

**Outcome 2 was exercised**: a second run reported `tables_created=0`, `tables_preexisting=8`, and
`seed_action=idempotent_replay_no_rewrite`.

**Outcome 3 was exercised too**, rather than merely asserted. The definition was mutated in memory and
the applier compared it against the lab: divergence was detected **even though every row count still
matched**, because the content hash catches a changed value that a count cannot. No `UPDATE` and no
`DELETE` was issued, and a re-verification afterwards confirmed the stored dataset was untouched.

**Correction policy: a scenario correction requires a new scenario version slug — never a rewrite.**
This is the same constraint the controlled schema lives under, where every writer is create-only with
no `UPDATE` path, and it is enforced here by the applier refusing to proceed rather than by
convention.

---

## 6. Credential posture

Two **new, dedicated, scenario-scoped** lab credentials. **No controlled-schema credential was
expanded**, and **no production credential was used, created, or altered.**

| credential | global | on `peak_lab_scenario.*` | `GRANT OPTION` | can see `peak_lab`? |
| --- | --- | --- | --- | --- |
| `peak_lab_scenario_loader` | `USAGE` only | `SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER` | **none** | **no** |
| `peak_lab_scenario_ro` | `USAGE` only | **`SELECT`** | **none** | **no** |

Verified by reading `SHOW GRANTS` back **as each credential in turn** after reduction. Each holds
**exactly one** database-level grant, on the scenario schema, and **neither can enumerate a single
`peak_lab` table** — isolation confirmed by measurement, not by grant text alone.

**This reduction mattered more than expected.** Newly provisioned service users on the lab platform
arrive holding **global `ALL PRIVILEGES` WITH `GRANT OPTION`** — including `CREATE USER` — which means
that as created, **both scenario credentials could read and write every controlled `peak_lab` table.**
Reducing them was not tidying; it was removing a live path from the scenario tooling into the
controlled schema. See §9.1 for the sequencing this required.

Both credentials are recorded in **out-of-repo environment files, mode `600`**, in the operator
credential directory, each setting **exactly one** variable, **single-quoted**, with a URL-encoded
password. **Two new variable names were introduced** rather than reusing the production-named
variables the other lab roles depend on:

| basename | variable |
| --- | --- |
| `peak-lab-scenario-loader.env` | `PEAK_LAB_SCENARIO_LOADER_URL` |
| `peak-lab-scenario-ro.env` | `PEAK_LAB_SCENARIO_RO_URL` |

**No repository tool reads either variable**, and none was changed to. This deliberately avoids
extending the Phase 82 §3 seam — where every lab DSN sits in a production-named variable and the
variable name cannot tell you which environment it points at — into the scenario path. The scenario
tooling is out-of-repo, so it can name its own variables honestly.

---

## 7. Verification

All verification below is **`SELECT`-only, under the read-only scenario credential.**

- `peak_lab_scenario` **exists**, `utf8mb4` / `utf8mb4_0900_ai_ci`
- **exactly the 8 expected tables**, all `InnoDB`, all `utf8mb4_0900_ai_ci`, 37 columns pinned `utf8mb4_bin`
- **no `alembic_version` table exists in `peak_lab_scenario`**
- **row counts match per table**, 120 rows total
- **all 33 control totals match**, and 7 were independently recomputed in SQL
- **content hash matches** across definition, database, and stored control total
- scenario row flagged **not production** and **not Alembic-managed**
- the scenario read-only credential **can see no `peak_lab` table**

**The controlled schema was re-read afterwards under its own read-only credential and is unchanged:**
19 base tables, head `014_engagement_classification`, `alembic_version` **1 row**, and **0 application
rows across all 18 controlled tables** — identical to the Phase 83 end state.

**Caption, required.** Under the *controlled* schema's read-only credential, `peak_lab_scenario`
reports as **not present**. That is least privilege behaving correctly — `peak_lab_verify_ro` holds no
grant on the scenario schema and therefore cannot enumerate it — **not evidence that the scenario
schema is absent.** Its existence is confirmed under the scenario credentials. Anyone reading a
`peak_lab_verify_ro` schema listing must not conclude from it that the scenario schema does not exist.

---

## 8. Non-claims and boundaries

- **No production access.** No production environment file sourced, no production credential used, no
  production database, service, project, schema, network, or console contacted or changed.
- **No live Alembic migration** — no `upgrade`, `downgrade`, or `stamp` against any target, lab or
  otherwise. **`peak_lab_scenario` is not Alembic-managed and has no `alembic_version` table.**
- **No migration `015`**, and no change to any migration, model, or application schema.
- **No write to any `peak_lab` controlled table** — re-verified as 0 application rows across all 18.
- **No Peak writer invoked and no Peak record created** — no Client, Engagement, intake note, source
  ingestion, evidence reference, review record, review bundle, report draft, capsule, client-facing
  output, or AgentNet publication record.
- **No dependency installed.** The scenario tooling uses only the existing environment.
- **No repository infrastructure added** — no migration, model, writer, allowlist entry, schema,
  operator, or harness. **Docs only.**
- **No scenario row body, seed body, extract, fixture, or external artifact committed** in any format.
- **The scenario data is not evidence.** It is internal synthetic lab source-system data. Measuring
  against it produces **lab-scenario values, never client evidence**, and never a finding.

---

## 9. Warnings and decisions needing review

1. **Newly created service users on this lab platform arrive with global `ALL PRIVILEGES` WITH
   `GRANT OPTION`.** This is the platform's default, not a misconfiguration introduced here, and it
   means **any future lab credential is over-privileged from the moment it exists until it is
   explicitly reduced.** Reduction must be treated as a mandatory provisioning step, and its result
   must be verified by connecting as the credential — not assumed. The same default applied to the
   Phase 83 credentials and was reduced there.
2. **The reduction required an unusual sequence, worth recording before anyone repeats it.** On this
   server a grantor carrying the platform's default partial revokes on internal schemas can issue
   `REVOKE ALL PRIVILEGES ON *.*` only against an account still holding the identical default set, and
   **that statement clears database-level grants as well as global ones.** Globals must therefore be
   stripped *first* and the database grant issued *afterwards*, by a second account that still holds
   `GRANT OPTION`. The read-only credential was recreated at platform defaults to act as that grantor,
   the loader was finalised through it, and the loader's residual database-scoped `GRANT OPTION` was
   stripped last. **A naive "revoke then grant to self" ordering silently leaves a credential with no
   privileges and no way to restore them.**
3. **The lab control-plane API returns a masked placeholder instead of a stored password.** Service
   credentials therefore **cannot be recovered from it** — they can only be reset. The environment
   files written by this phase are the operative record of the two scenario passwords; if they are
   lost, the credentials must be reset rather than looked up. **The service administrator password was
   deliberately not reset**, so nothing the operator relies on was rotated.
4. **The scenario schema is unprotected by the Phase 84 guard.** That guard covers Alembic only, and
   `peak_lab_scenario` is not Alembic-managed, so nothing in source prevents a future tool from being
   pointed at the wrong schema. Protection here rests on the credential boundary — the scenario
   credentials cannot see `peak_lab`, and the controlled credentials cannot see the scenario schema —
   which is a real control, but a different one, and it should be understood as such.
5. **Scenario completeness flags are stored, not derived at read time.** They were checked against the
   columns they describe before insertion and re-checked in the database afterwards, but a future
   measurement phase should **recompute from the underlying columns** rather than trust the flag, or
   the flag becomes an assumption the measurement is supposed to be testing.
6. **All Phase 83 §7 open items remain open** — unverified server-version parity (the lab runs MySQL
   8.4 and production's version was not read), verifier and gate output that says "production" when
   pointed at the lab, the credential-exposure cause mitigated only by convention, the inert
   `mysql-parity-staging` target, and the stale 211/308 figure in
   `GOVERNED_MYSQL_COLLATION_POLICY.md`. **Phase 85 addresses none of them and closes none of them.**
   Phase 83 §7.7 remains closed by Phase 84.

---

## 10. Posture after Phase 85

- **The repository is unchanged apart from documentation.** Repo head stays
  `014_engagement_classification`, **14 migrations, 18 controlled tables, 12 writers**, no migration
  `015`, and **no standing production write enablement** — the Phase 51 gate still reports
  `safe_to_write_production_now=false`.
- **`peak_lab` is unchanged** — head `014`, 18 controlled tables plus `alembic_version`, **0
  application rows**.
- **`peak_lab_scenario` exists and is seeded** with `internal_test_inventory_ops_v1`, 120 rows, hash
  `18459dc1…`, under two least-privilege scenario credentials that cannot reach the controlled schema.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** A seeded scenario
  does not reopen it. The reviewed Phase 79 source remains **source-only, not evidence**. **R1 remains
  provisional**, and the location finding stays **data-readiness and reliability only, never inventory
  accuracy.** The **R5 WMS scope clarification remains a reviewed scope-blocker enumeration only** and
  the **Phase 64 R5 export remains uncollected**. **R3–R7 remain deferred.** The Phase 74 outline is
  unmodified and `fnd_000` remains `blocked_no_review_support`.
- **Report finalization, client-facing output, capsule publication, and AgentNet resolver publication
  remain unauthorized.**

---

## 11. What a later phase may do, with separate approval

**Nothing below is authorized by Phase 85.**

Future evidence, extraction, and source-ingestion phases **may now measure against this scenario**,
because a deterministic, hashed, mixed-quality dataset now exists to measure against. **Each such
phase still requires its own separate approval**, and two constraints carry forward unchanged:

- **The writer-enablement decision gate is environment-blind and hardcodes every authorization to
  `false`.** Authorizing any lab write through a Peak writer is a deliberate source edit with its own
  review; it cannot be flipped by an environment variable, and it did not happen here.
- **Every writer is create-only with no `UPDATE` path**, so a corrected measurement means a new
  version slug, never a rewrite — matching the scenario correction policy in §5.

**Measured values obtained against this scenario are lab-scenario values.** They are not client
evidence, they do not support a finding, and they must never be presented as either.

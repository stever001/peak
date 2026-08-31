# Phase 88 — The Read-Only Lab Scenario Measurement Pass

Phase 88 measured the seeded lab scenario `internal_test_inventory_ops_v1` **read-only**, from the
scenario read-only credential, to establish whether it can support future Peak evidence and
source-ingestion work. Repo baseline at entry: `fc943f5`, Alembic head `014_engagement_classification`,
14 migrations, 18 controlled tables, 12 writers.

**Every statement issued in this phase was a `SELECT`.** **No write occurred to `peak_lab_scenario`**,
**no write occurred to `peak_lab`**, **no Peak writer was invoked**, **no Peak record was created**,
**no production access occurred**, **no live Alembic migration ran**, and **no migration `015` was
created**. No schema was created, altered, or dropped; no credential was created, reset, or regranted.

**This document carries aggregates only.** No row body, identifier, secret, DSN, host, port, provider
name, credential path, or environment value appears here or in the repository. Measurements are
**internal synthetic lab-scenario values**; they are not client evidence and they do not prove
real-client readiness.

---

## 1. What was measured, and from where

| property | value |
| --- | --- |
| schema measured | `peak_lab_scenario` (lab-only, not Alembic-managed, not production) |
| scenario | `internal_test_inventory_ops_v1`, version `v1` |
| credential | the scenario **read-only** role |
| statements | `SELECT` only |
| rows read | 120 (87 data rows + 33 control totals) |
| rows written | **0** |

A second, optional read-only pass confirmed the **controlled** lab schema is untouched. It is
reported in §7.

---

## 2. Credential posture, verified before measuring

Seventeen **value-free** structural checks passed against the scenario read-only environment file —
existence, mode `600`, exactly one variable, the expected variable name, single-quoted value, scheme,
role name, target database, and the presence (never the content) of password, host, port and CA path.
The file was parsed in memory; **no value was printed, echoed, or logged**, and the target was
confirmed to be neither the controlled lab schema, nor the platform default schema, nor anything
carrying a production marker.

Privileges were then read back **as the credential itself**:

| check | result |
| --- | --- |
| global privilege | `USAGE` only |
| database-level grants | exactly one, `SELECT`, on the scenario schema |
| `GRANT OPTION` | none |
| grants referencing the controlled lab schema | none |
| controlled-schema tables visible to this credential | **0** |
| controlled lab schema enumerable by this credential | **no** |

**Five write attempts were issued deliberately as a negative control** — `INSERT`, `UPDATE`,
`DELETE`, `CREATE TABLE`, `DROP TABLE` — and **all five were refused by the server** with a
permission error. Read-only posture is therefore established by **measurement, not by grant text
alone**. Nothing was created or removed by these probes; each was rejected before execution.

---

## 3. Scenario integrity

| check | result |
| --- | --- |
| expected 8 tables present, all `InnoDB` | pass |
| `alembic_version` table in the scenario schema | **absent**, as required |
| rows: 120 total, 87 data rows | pass |
| scenario flagged not production, not Alembic-managed **in the data** | pass |
| stored control totals | 33 |
| **content hash matches the Phase 85 published hash** | **pass** |
| **all 32 stored counts/sums recomputed from the rows and matched** | **pass**, 0 mismatches |
| every inventory row resolves to an item-master row | pass, 0 orphans |
| no row flagged location-resolvable is in fact unresolvable | pass, 0 contradictions |

The hash is stored under a single control of kind `hash` and agrees with the value Phase 85
published. **The scenario is measurable repeatably**: the dataset is unchanged since seeding, and
every published control total was independently reproduced by aggregating the rows rather than by
reading the stored total.

---

## 4. Aggregate measurements

### 4.1 Source systems and the R8 authority map

| measure | value |
| --- | ---: |
| source systems | 4 |
| distinct system kinds / roles / extract capabilities | 4 / 4 / 4 |
| declared system-of-record systems | 2 |
| authority-map rows | 10 |
| distinct record domains | 10 |
| domains **resolved** | 4 |
| domains **contested** | 3 |
| domains **unresolved** | 3 |
| precedence rule documented | 4 |
| domains with a measurable authoritative source | **4 of 10** |
| domains intentionally left open | **6 of 10** |

Each of the four source systems carries a distinct kind, role, and extract capability, so extract
feasibility varies by system by design — one full export, one partial, one manual, one screen-only.

### 4.2 Item master (R2)

| measure | value |
| --- | ---: |
| items | 10 |
| flagged complete / incomplete / ambiguous | 5 / 3 / 2 |
| status active / inactive / unset | 8 / 1 / 1 |
| all four core attributes present | 6 |
| missing at least one core attribute | 4 |
| `base_uom` missing | 2 |
| case quantity null or non-positive | 4 |
| weight missing or non-positive | 3 |
| **duplicate item codes** | **0** |
| lot-controlled / serial-controlled | 2 / 1 |

**A reconciliation worth carrying forward.** The seeded flag says 5 items are complete; a
presence-only check on the four core attributes says 6. These do not conflict. All 5 flagged
`complete` carry all four attributes, none of the 3 flagged `incomplete` do, and **1 of the 2
flagged `ambiguous` carries every attribute while still being unusable** — `ambiguous` encodes a
*semantic* conflict (the seeded unit-of-measure conflict), not a missing value.

**A future readiness rule that tests only for attribute presence will over-count usable items.** It
must consult the completeness classification as well. This is exactly the kind of defect the mixed
scenario was seeded to expose, and it is now measurable.

### 4.3 Location/bin model (R9)

| measure | value |
| --- | ---: |
| locations | 16 |
| structure complete / partial / absent | 9 / 3 / 4 |
| full aisle/bay/level/bin structure (computed) | 9 |
| missing at least one structural component | 7 |
| zone code present | 15 |
| pickable | 9 |
| **duplicate location codes** | **0** |
| **usable for location-attributed evidence** | **9 of 16** |

Here the seeded flag and the computed structure agree exactly at 9 — unlike R2, the location
classification is fully derivable from attribute presence.

### 4.4 Inventory snapshot (R1)

| measure | value |
| --- | ---: |
| inventory rows | 32 |
| flagged complete / incomplete / ambiguous | 20 / 10 / 2 |
| SKU resolvable / unresolved | **32 / 0** |
| location resolvable / unresolved | 25 / 7 |
| — of which: no location code at all | 3 |
| — of which: names a location code absent from the model | 4 |
| both SKU and location resolved | 25 |
| quantity present / absent | 29 / 3 |
| unit of measure missing | 2 |
| blocked by item-master gaps | 11 |
| blocked by location-model gaps | 7 |
| **fully usable for location-attributed evidence** | **14 of 32 (43.8%)** |
| on-hand quantity sum | 2201.000 |

Every inventory row resolves to an item, so **SKU attribution is unblocked**. Location attribution is
the constraint: 7 rows cannot be placed, and once item-master quality and quantity presence are also
required, **fewer than half the rows survive**.

### 4.5 Receiving and putaway (R5)

Measured **per event type**, because a receipt event legitimately carries no putaway timestamp and a
flat "both timestamps present" test understates readiness:

| measure | putaway | receipt |
| --- | ---: | ---: |
| events | 7 | 7 |
| `received_at` present | 7 | 6 |
| `putaway_at` present | 6 | 0 (by design) |
| flagged timing complete | 5 | 6 |

| measure | value |
| --- | ---: |
| events | 14 |
| timing complete / incomplete / ambiguous | 11 / 2 / 1 |
| location complete / incomplete / ambiguous | 11 / 2 / 1 |
| SKU resolvable / unresolved | **14 / 0** |
| target location resolvable / unresolved | 11 / 3 |
| no target location code | 2 |
| **putaway events usable for putaway-process evidence** | **3 of 7** |
| receipt events usable for receipt-process evidence | 5 of 7 |
| events carrying both timestamps in valid order | 5 |
| **events whose putaway precedes its receipt** | **1** (seeded defect, now measurable) |
| quantity sum | 2130.000 |

The seeded ordering defect is detectable by measurement, which is the point of having seeded it.

---

## 5. Evidence-readiness matrix

**Scenario-derived only.** "Measurable" means the scenario can support a *computation*; it does not
mean a Peak evidence record may be created, and it makes no claim about any client.

| domain | measurable? | aggregate support | blockers | could support a future evidence reference? |
| --- | --- | --- | --- | --- |
| **R1** current inventory by SKU/location | **partial** | 32 rows; SKU 32/32; location 25/32; 14 fully usable (43.8%) | 7 unresolvable locations (3 absent, 4 dangling); 11 rows behind item-master gaps; 3 rows without quantity | Yes, as a *lab-scenario* coverage measurement, subject to separate approval |
| **R2** SKU / item master | **partial** | 10 items; 5 complete; 0 duplicates | 3 incomplete, 2 ambiguous; presence-only checks over-count by 1 | Yes, with a rule that reads the completeness class, not just attribute presence |
| **R5** receiving / putaway | **partial** | 14 events; SKU 14/14; putaway 3/7 usable; receipt 5/7 usable | 3 unresolvable target locations; 2 missing destination; 1 invalid receipt→putaway ordering | Yes, for putaway-process feasibility only; the timing population is small |
| **R8** system-of-record authority map | **partial** | 10 domains; 4 resolved with a documented precedence rule | **6 of 10 domains contested or unresolved by design** | Only for the 4 resolved domains. **R8 authority precedence remains unconfirmed**; Phase 88 does not reopen it |
| **R9** location / bin model | **partial** | 16 locations; 9 complete; 0 duplicates; flag agrees with computed structure | 3 partial, 4 absent structures | Yes, as a location-model readiness measurement |
| **R10** answer set / location-readiness interpretation | **partial** | Derivable from R1 ∩ R2 ∩ R9: **43.8% of inventory rows are location-attributable** | Inherits every R1, R2 and R9 blocker; no independent R10 population exists in the scenario | Yes, as a *derived* readiness rate, explicitly labelled lab-scenario |

**No domain measures "yes" and none measures "no."** Every domain is *partial* — which is the
scenario behaving as designed. A dataset in which everything resolved could not demonstrate that a
readiness check works.

---

## 6. What this does and does not establish

**Established.** The scenario is repeatably measurable from the read-only credential; its content
hash and all 33 control totals hold; referential integrity holds; and each of R1, R2, R5, R8, R9 and
R10 yields deterministic aggregate coverage figures with named blockers.

**Not established, and not claimed.**

- **Nothing here is client evidence.** Every figure is an internal synthetic lab-scenario value.
- **The scenario does not prove real-client readiness**, and no measured rate should be presented as
  a client finding, a benchmark, or a projection.
- **R8 authority precedence remains unconfirmed and R8 remains non-authoritative.** Measuring a
  seeded authority map does not settle authority.
- **R1 accuracy is not addressed.** Coverage is not accuracy.
- **R5 remains a scope-blocker enumeration**; the Phase 64 R5 export remains uncollected.
- **R3–R7 remain deferred**, and the Phase 74 outline remains an outline.
- **Creating any Peak evidence, source-ingestion, review, or intake record remains separately
  unauthorized.**
- **Writer enablement remains separately unauthorized.** The decision gate is environment-blind and
  hardcodes every authorization to `false`; enabling a writer is a deliberate source edit with its
  own review, and it did not happen here.

---

## 7. The controlled lab schema is unchanged

Confirmed afterwards under the **controlled** schema's own read-only credential, `SELECT` only:

| check | result |
| --- | --- |
| grants held | `SELECT` and `USAGE` only; no `GRANT OPTION` |
| base tables | 19 (18 controlled + `alembic_version`) |
| Alembic head | `014_engagement_classification`, 1 row |
| **application rows across all 18 controlled tables** | **0** |
| controlled tables holding any row | **0** |

Identical to the Phase 83 and Phase 85 end state.

**Caption, required — unchanged from Phase 85.** Under the controlled schema's read-only credential,
the scenario schema reports as **not present**. That is least privilege behaving correctly, **not
evidence that the scenario schema is absent**.

---

## 8. Warnings and decisions needing review

1. **The Phase 82 §3 variable-naming seam is still live and was encountered directly.** The lab
   read-only credential file sets a **production-named variable** while pointing at the lab schema.
   Nothing here changed it, and this phase guarded against it by asserting the target database and
   role name **before** opening the connection rather than trusting the variable name. The seam
   remains a standing trap for any future operator or tool that reads the variable name as an
   environment label. The scenario credentials, which name their own variables honestly, show the
   better pattern.

2. **A presence-only readiness rule would over-count usable items by 1 in 10.** §4.2 quantifies it.
   Any future readiness check must consult the completeness classification, not attribute presence
   alone. This is a design input for the next phase, not a defect in the scenario.

3. **The R5 timing population is small** — 7 putaway events, 3 usable. Conclusions drawn from it
   should be treated as directional even within the lab.

4. **R10 has no independent population.** Its readiness rate is derived from R1 ∩ R2 ∩ R9 and
   inherits all of their blockers; it should never be cited as a separate measurement.

5. **Five write attempts were deliberately issued and refused.** This was an intentional negative
   control to prove read-only posture by measurement. It is recorded here so that a reader of the
   server's audit log finds the explanation rather than an unexplained set of denied statements.

---

## 9. Posture after Phase 88

- **The repository is unchanged except for documentation.** Alembic head `014_engagement_classification`,
  14 migrations, 18 controlled tables, 12 writers, no migration `015`.
- **`peak_lab` is unchanged** — head `014`, 18 controlled tables, **0 application rows**.
- **`peak_lab_scenario` is unchanged** — 120 rows, content hash unchanged and re-verified.
- **No Peak record exists that did not exist before**, in any environment.
- **Production was not contacted.**

## 10. What a later phase may do, with separate approval

**Nothing below is authorized by Phase 88.**

A future phase may propose creating Peak evidence or source-ingestion records **from these
measurements**, in the lab, under its own approval, naming the writer, table, action, scope,
idempotency key and cleanup posture in advance. Two constraints carry forward unchanged: the
writer-enablement gate must be deliberately edited and reviewed, and every writer is create-only,
so a corrected measurement means a new version slug rather than a rewrite.

**Measured values obtained against this scenario are lab-scenario values.** They are not client
evidence, they do not support a finding, and they must never be presented as either.

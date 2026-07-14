# Source System Capsulization

The **intended future** path for turning client source material into grounded resolver
capsules for internal Peak AI workflows. **Architecture documentation only** — no
ingestion pipeline, capsulization process, resolver, or AgentNet integration is
implemented. **Do not read this as implementation.**

## Source locations

Client operational facts originate in source systems and materials. Sources that may
become inputs for capsulization include:

- **docs** (procedures, SOPs, spreadsheets),
- **HTML / internal pages** (intranet, internal apps),
- **telemetry**,
- **inventory events**,
- **ERP / WMS exports**,
- **reports**,
- **operational logs**,
- **system screenshots** (only where approved).

Each is represented (as a pointer, not embedded content) by a `SourceSystemReference`
([`../schemas/source-system-reference.schema.json`](../schemas/source-system-reference.schema.json)),
held in controlled engagement storage — never committed to the repo.

## From source to capsule (intended flow)

```
source location (ERP/WMS export, report, telemetry, doc, HTML, log, screenshot*)
   -> SourceSystemReference          (pointer + authorization + sensitivity)
   -> capsulization                  (intended future — extract, structure, ground)
   -> ResolverCapsuleRecord          (private, governed grounding capsule)
   -> internal Peak AI workflows     (grounded, under authorization)

* screenshots only where approved
```

## What capsulization must preserve

Whenever capsulization is built, it must preserve:

- **Source references** — which `SourceSystemReference`(s) a capsule came from.
- **Evidence links** — the `EvidenceReference` ids grounding the capsule.
- **Timestamps** — when source material was captured and when the capsule was created.
- **Authorization scope** — the authorization under which the data may be used.
- **Review status** — the governance review state.

These preservation requirements are why the contracts
([`source-system-reference`](../schemas/source-system-reference.schema.json),
[`resolver-capsule-record`](../schemas/resolver-capsule-record.schema.json)) are defined
now, before any pipeline exists.

## Status

Capsulization, resolver, and AgentNet grounding are **intended future architecture, not
implemented**. Nothing in this repository ingests, capsulizes, stores, or grounds any
source material. Client source data is handled only in controlled engagement storage
under authorization (see [`DATA_HANDLING_POLICY.md`](DATA_HANDLING_POLICY.md) and
[`CONTROLLED_DATA_ARCHITECTURE.md`](CONTROLLED_DATA_ARCHITECTURE.md)). Controlled
ingestion from client source systems is a **later** stage of the database plan (see
[`DATABASE_IMPLEMENTATION_PLAN.md`](DATABASE_IMPLEMENTATION_PLAN.md)), tracked by a
`SourceIngestionRecord` ([`DATABASE_RECORD_MODEL.md`](DATABASE_RECORD_MODEL.md)).

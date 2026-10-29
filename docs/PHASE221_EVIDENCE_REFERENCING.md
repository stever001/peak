# Phase 221 — Evidence Referencing

Back to [`PHASE_INDEX.md`](PHASE_INDEX.md). Baseline `0001174`.

## Purpose

Phase 220 lets a consultant capture photos and document photos on a task. Phase 221 lets the
consultant say which of those captures support an observation they wrote, and shows that link
later in the internal assessment:

```
Observation (consultant's own words) → zero or more captured items of the same engagement
```

**Status: implemented, not yet committed or deployed.**

## Rule

Evidence remains source material. A link is the consultant's statement that a capture supports
their observation. It never:
- creates an observation, finding or recommendation;
- adds words to an observation;
- changes readiness, task status or recommendation eligibility;
- becomes governed assessment evidence (`evidence_references`);
- leads Peak to read, parse or interpret the capture (no OCR, CV or inference).

## What it is not

There is no unlink, re-link, scoring, automatic suggestion, client upload, PDF, report image
embedding, publication, or retention/delete system. A link is not an audit or compliance record.

## Existing linkage

None was reusable:
- `evidence_references` is the governed assessment-evidence chain. Phase 220 deliberately keeps
  captures out of it.
- `phase_task_evidence.task_record_id` links a capture to a task record, not to an observation.
- `roadmap_items.source_observation_ids` is a JSON list on another record type.

So Phase 221 adds the smallest explicit link table.

## Data model (migration 024)

One new table, `observation_evidence_links`. It is insert-only: an ORM listener refuses update and
delete, singly and in bulk. It is classified `append_only`, so the runtime role needs no UPDATE
grant. No existing table changes.

| Column | Meaning |
|---|---|
| `id` | `oevl_<16 hex>` |
| `client_id`, `engagement_id` | Copied from the observation |
| `observation_id` | A `discovery_observations` row |
| `evidence_id` | A `phase_task_evidence` row of the same engagement |
| `linked_by_consultant_id` | The signed-in consultant; `created_at` says when |

`UNIQUE(observation_id, evidence_id)` (`uq_observation_evidence_links_pair`) links a pair at most
once. There are no foreign keys, as with every workspace table. All id columns are governed
identifiers (`utf8mb4_bin` on MySQL) under the existing `_id` collation pattern, so the collation
audit needed no change.

## Rules on saving

`evidence_ids` is accepted on `POST /engagements/{id}/observations` and
`PATCH /observations/{id}`. The links are written in the **same transaction** as the observation:
- Each capture must belong to the observation's engagement (`invalid_link`).
- Each capture must be current, not replaced (`evidence_replaced`).
- A pair cannot be linked twice, and the same id cannot be chosen twice (`duplicate_link`).
- At most 50 links per save.

Any refusal refuses the whole save: no observation, no edit, no link. A PATCH adds links; it never
removes one. The linking consultant is always the signed-in consultant.

## API

| Route | Auth | What it does |
|---|---|---|
| `GET /engagements/{id}/evidence` | session | `available`: current captures, newest first. `links`: each observation's linked captures. Every item has a 15-minute `content_path` |
| `POST /engagements/{id}/observations` | session | As before, plus optional `evidence_ids` |
| `PATCH /observations/{id}` | session | As before, plus optional `evidence_ids` (adds only) |
| `GET /engagements/{id}/assessment` | session | As before, plus `observation_evidence` (links by observation id) **beside** `assessment` |

Each item carries:
- kind and caption;
- the originating task (id, title, phase);
- who added it and when;
- `superseded` and `superseded_by`;
- for a link, who linked it and when.

Items never carry a storage key, file name or hash. Content is served by the Phase 220
`/evidence-content/{token}` route unchanged.

## Consultant workflow

- **Add observation** (engagement → Discovery): below the observation fields there is a "Supporting
  photos and documents (optional)" list. Each item shows a thumbnail, caption, kind, originating
  task (linked) and date, with a checkbox. The observation text stays empty until the consultant
  writes it. Nothing is prefilled from a caption.
- **Observation cards** show their linked captures.
- **Edit observation** shows the existing links above the form. The picker offers only captures not
  yet linked.
- Linking is optional everywhere. If the API has no Phase 221 route, the pages show and save
  observations exactly as before. The form sends `evidence_ids` only when one is chosen.

No "Use in observation" shortcut was added to the task page.

## Assessment traceability

Each discovery-derived finding card shows "Supporting photos and documents (n)". For each item it
shows the caption, kind, originating task, date and "Open full size". The links are returned
outside the assessment dataclasses. So:
- the assessment, its findings, low-hanging fruit and evidence-backed findings are unchanged;
- recommendations and the Markdown are unchanged;
- the Final Report (JSON, Markdown, DOCX, stored versions) is unchanged and embeds no image.

## Supersession

A link names the exact capture chosen. If that capture is later replaced on its task, the link
stays on the original. It is shown as "Replaced on its task since it was linked" and still opens.
The newer capture is never substituted. It becomes available to link separately. A replaced
capture cannot be newly linked.

## Validation

`tests/validate_phase221_evidence_referencing.py` (`make validate-phase221`) covers:
- **migration 024:** upgrade, single head, column parity, UNIQUE pair, downgrade, no data;
- **persistence policy:** `append_only`, one create action, ORM refuses update and delete;
- **links:** no links, one link, several links, adding on edit, the same capture on two
  observations;
- **refusals:** duplicate, repeated id, another engagement's capture, unknown and replaced captures,
  and an atomic refusal that writes nothing;
- **supersession:** the link is kept and labelled, nothing is substituted, the newer capture is
  offered;
- **assessment:** count, caption, task, and content opening;
- **no leaks:** no storage key or file name in any response;
- **boundary:** only the link table changes. The finding, evidence-backed material, Final Report
  recommendations, task status and readiness are unchanged, and nothing linked appears inside the
  assessment or report;
- **static UI:** picker, graceful degrade, no generated wording, the advisory-boundary scan.

## Production sequencing (when approved)

The API must not run against production before migration 024 exists, because its engagement
evidence read would fail. The web may go first: without the route, linking is hidden.

1. Commit with `[skip render]`.
2. Apply migration 024 with `peak_prod_migrate`. The runtime role needs no new grant.
3. Move `EXPECTED_ALEMBIC_HEAD` to `024_observation_evidence_links` in a follow-up commit. Run the
   verifier and the Phase 50 gate.
4. Deploy the API, then confirm the web.

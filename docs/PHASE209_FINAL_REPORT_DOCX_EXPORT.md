# Phase 209 — Final Report DOCX export

Phase 208 composed the internal assessment into a deterministic Final Report. Phase 209 lets a
consultant **download that same report as an editable Word document**. It renders; it does not
compose. No new report logic, no LLM, no stored export, no client-facing approval, and no production
deploy.

Baseline `1018db2` — *Add Phase 208 final report foundation*.
Index: [`PHASE_INDEX.md`](PHASE_INDEX.md).

**Status: built and validated locally. Not deployed.** Production stays at Phase 207, schema
`017_discovery_workflow`, and Render Auto-Deploy remains **OFF**.

> **OPEN ITEM, carried forward and still open: production Admin acceptance is pending provisioning
> of `admin@peakinventorysolutions.com`.** Authenticated production discovery, assessment and report
> acceptance remain pending for the same reason. No temporary Admin may be created.

## What was built

| Piece | Where |
|---|---|
| DOCX renderer | `peak/reports/final_report_docx.py` — `render_final_report_docx(report)`, `final_report_docx_filename(report)` |
| Read-only export endpoint | `GET /engagements/{id}/final-report.docx` in `peak/consultant_api/app.py` |
| Download control | **Download DOCX** on `/engagements/[id]/final-report` |
| Web pass-through | `web/app/(workspace)/engagements/[id]/final-report/docx/route.ts` (GET only) |
| Validation | `tests/validate_phase209_final_report_docx_export.py` (`make validate-phase209`) |

```
engagement_id
  -> build_consultant_internal_assessment          (Phase 119/206, unchanged)
  -> compose_final_report(assessment, engagement)   (Phase 208, unchanged)
  -> render_final_report_markdown(report)           (Phase 208)  -> JSON route
  -> render_final_report_docx(report)               (Phase 209)  -> DOCX route
```

Both API routes share one helper (`_final_report`) that runs the assessment and the Phase 208
composer, so the DOCX is rendered from **the same `FinalReport` object** the page shows. The
renderer imports nothing from `peak.db`, opens no connection, re-queries nothing, and has no report
model of its own. It does not filter or reword recommendations: it prints
`report.recommendations.recommendations`, which Phase 208 already restricted to Phase
117/118-eligible findings.

## Renderer approach

**Standard library only — no new dependency.** The document is written as plain WordprocessingML
(`zipfile` + escaped XML) rather than through `python-docx`, which is not installed and would have
added a package (and `lxml`) to the Render build. The package holds seven parts: content types,
relationships, `document.xml`, `styles.xml`, `numbering.xml` (bullets) and `footer1.xml`.

**Deterministic.** Zip entries carry a fixed timestamp and there is no `docProps/core.xml` creation
time, so the same report always yields the same bytes. The harness checks this, and repeated
downloads are byte-identical.

**Centralized styles.** Every format lives once in `styles.xml`: Title, Subtitle, Heading 1–3,
North Star, Material label, Notice, List Bullet, Detail, Table Text, Footer, and one `Peak Table`
table style. Body paragraphs only name a style, so a consultant restyling the document in Word
changes it everywhere. Table borders are also repeated on each table, because some readers
(Google Docs, Quick Look) ignore table styles. No branding assets, images or theme files.

## Document structure

- **Title page:** "Final report", client · engagement, North Star (+ context), a status table
  (internal draft, client-facing no, approved for client use no, requires human review yes), and the
  report status notice. Page break.
- **The six Phase 208 sections, in `SECTION_ORDER`,** each a Heading 1 using the report's own
  section titles: executive overview, discovery summary, low-hanging-fruit opportunities,
  evidence-backed findings, internal recommendations, limitations and human review. Content matches
  the Markdown renderer line for line: coverage and finding attributes as two-column tables, findings
  and recommendations as bullets with detail lines.
- **Material labels:** discovery and low-hanging-fruit sections open with *Material: consultant
  working material — not reviewed evidence*; evidence and recommendation sections with *Material:
  evidence-backed, governed*.
- **Low-hanging fruit:** the Phase 206/208 grouping text, the not-a-ranking/not-ROI statement, then
  one Heading 3 per value/effort group (*Value High · Effort Low*), in display order. No numbers,
  ranks or scores.
- **Footer on every page:** *Internal draft · Not client-facing · Requires consultant review · Page
  N of M*.

## API and UI

- `GET /engagements/{id}/final-report.docx` → `200`,
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
  `Content-Disposition: attachment; filename="final-report-<client>-<engagement>.docx"` (ASCII
  slugs), `Cache-Control: no-store`. Authenticated consultant required (401); unknown or not-visible
  engagement 404 through the same visibility path as the assessment. POST/PUT/PATCH/DELETE → 405.
- The browser cannot call the API directly (the session cookie is forwarded server-side by
  `apiFetch`), so the **Download DOCX** link points at a Next route handler that streams the API
  response through. 401 → `/login`, 404 → 404, any other method → 405. No new page.
- The button sits beside *Internal assessment* in the page header; it stacks full-width on phone.

## Wording correction

Phase 208's status text said the report was "not exported", which became false here. It now reads
*"Not client-facing and not approved for client use; an exported copy is still this internal
draft."* in `REPORT_STATUS_TEXT` and in the page banner. No test asserted the old wording, and no
composition logic changed.

## What was not built

No PDF, proposal, billing, signatures, LLM synthesis, stored export, migration 018, new table, write
action, or production deploy.

## Validation

- `tests/validate_phase209_final_report_docx_export.py` — PASS. Covers: a valid, deterministic DOCX
  from a composed `FinalReport`; the six Heading 1s equal the report's section titles in order; the
  North Star on the title page and in the overview; only the eligible recommendation appears (a
  hand-built recommendation for a blocked finding does not) and the API document matches the
  report's recommendations; working-material and governed labels sit only in their own sections, with
  no discovery statement in the evidence or recommendation sections; low-hanging-fruit grouping and
  not-a-ranking text; the footer; the endpoint's media type, attachment filename, 401/404/405 and
  byte-identical repeats; a no-discovery engagement still exports; no migration 018, renderer imports
  only stdlib and sibling report modules, no allowlist write action.
- `npm run build` and `npm run lint` — clean; `/engagements/[id]/final-report/docx` in the route
  table.
- `make validate` — exit 0, 82 harness runs, all PASS. Run because this phase adds a Makefile target and edits
  `docs/IMPLEMENTATION_PLAN.md`, which older harnesses scan.
- Local end-to-end smoke run (uvicorn + `next start` on throwaway SQLite): signed-in download through
  Next returned 200 with the DOCX type and filename, and `file` identified it as *Microsoft Word
  2007+*; the page's Download DOCX link was present; no cookie or a forged cookie → `/login`; unknown
  engagement 404; POST 405. The throwaway database was deleted afterwards.

**Next:** internal review of the exported document. PDF and client-facing approval are later,
separately approved phases; deploying Phases 208–209 is its own cutover.

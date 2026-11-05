#!/usr/bin/env python3
"""Phase 226 — Lead review of an observation (offline; temporary SQLite and a temporary local store only).

Proves:

1. **Schema.** One additive migration (026) creating exactly ``observation_lead_reviews``; append-only
   in the model, the allowlist and the persistence policy; the production verifier pin stays at 025.
2. **The rule.** Eligibility of a discovery-derived finding is a fixed function of the current Lead
   review: it needs one, it must approve, its reliability must be medium or high, and it must have
   approved the statement exactly as it stands. A review of another observation or engagement never
   counts. The Phase 117 evidence rule and the report composers are byte-identical to the baseline.
3. **Authority.** Logged out 401. No Lead assigned, a consultant who is not the Lead, an Admin who is
   not the Lead, and the Lead of another engagement are all refused, and nothing is written. A stale
   text or a stale review is refused. A repeat writes nothing.
4. **What stays unchanged.** The observation, evidence and review records of the governed evidence
   path, tasks, phases, readiness, artifacts, packages, the Final Report and every recommendation.
   Reads write nothing.
5. **Assessment.** The eligibility appears beside the finding, never inside it, and no recommendation
   is drafted. An assessment with no Lead review is byte-identical to the baseline's.
6. **Static UI.** The panel says what the action means and that it creates no recommendation.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)
import validate_phase223_phase_work_record as p223  # noqa: E402  (shared fixtures)
from _schema_history import head_descends_from  # noqa: E402

REVISION = "026_observation_lead_reviews"
TABLE = "observation_lead_reviews"
BASELINE = "c18e317"
PANEL = "web/components/observation-lead-review.tsx"
OBSERVATION_PAGE = "web/app/(workspace)/observations/[id]/edit/page.tsx"
#: Files whose bytes must equal the baseline: the Phase 117/118 evidence rule and recommendation,
#: the Final Report composers and renderers, the evidence reader, and artifact approval and release.
UNCHANGED = (
    "peak/reports/packet_view_report.py", "peak/reports/packet_view.py",
    "peak/reports/persisted_packet_view.py", "peak/db/engagement_packet_reader.py",
    "peak/reports/final_report.py", "peak/reports/final_report_html.py",
    "peak/reports/final_report_docx.py", "peak/reports/release_presentation.py",
    "peak/workspace/approvals.py", "peak/workspace/artifacts.py",
    "peak/workspace/engagement_phases.py", "peak/db/review_writer.py", "peak/db/evidence_writer.py",
)
#: Assessment Markdown, Final Report Markdown and content hash prefixes for a fixed engagement with
#: no Lead review, rendered by the baseline code (``c18e317``). Interviews only / some outside.
BASELINE_HASHES = {
    False: ("5414c64b0bbaf571", "c67941bc04387a17", "4dd9e1b83146bd09"),
    True: ("45113fc04a355702", "4b7ab652d7fa314d", "fe8bd2c51f59cbaa"),
}
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


code, read, alembic = p220.code, p220.read, p220.alembic
_snapshot = p223._snapshot


def _changed(before, after):
    return {t for t in after if before.get(t) != after[t]}


# --------------------------------------------------------------------------- 1. schema


def schema_checks(tmp):
    print("\n[1. schema: one additive, append-only table]")
    import sqlalchemy as sa

    from peak.db import models as m
    from peak.persistence import allowlist, runtime_persistence as rp

    db = os.path.join(tmp, "schema.sqlite3")
    alembic(db, "upgrade", "025_observation_task_origins").check_returncode()
    engine = sa.create_engine(f"sqlite:///{db}")

    def columns():
        insp = sa.inspect(engine)
        return {t: sorted(c["name"] for c in insp.get_columns(t)) for t in insp.get_table_names()}

    before = columns()
    up = alembic(db, "upgrade", REVISION)
    after = columns()
    check("upgrade to 026 creates exactly observation_lead_reviews",
          up.returncode == 0 and set(after) - set(before) == {TABLE})
    check("no existing table or column is altered",
          all(after[t] == before[t] for t in before))
    check("the migrated columns match the model",
          set(after[TABLE]) == set(m.Base.metadata.tables[TABLE].columns.keys()))
    check("026 revises 025 and the head is 026 or descends from it",
          "down_revision = \"025_observation_task_origins\"" in read(f"alembic/versions/{REVISION}.py")
          and head_descends_from(REPO_ROOT, REVISION))
    down = alembic(db, "downgrade", "025_observation_task_origins")
    check("downgrade removes only that table", down.returncode == 0 and columns() == before)
    engine.dispose()
    body = read(f"alembic/versions/{REVISION}.py").split('"""', 2)[2].lower()
    check("the migration writes no data", "insert" not in body and "bulk_insert" not in body
          and "execute(" not in body)
    check("the production verifier pin stays at 025",
          'EXPECTED_ALEMBIC_HEAD = "025_observation_task_origins"'
          in read("tools/production_mysql_collation_verify.py"))
    actions = [(t, a) for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS if t == TABLE]
    check("one create action with exactly the review's columns",
          actions == [(TABLE, "create_observation_lead_review")]
          and allowlist.WORKSPACE_WRITE_COLUMNS[actions[0]] == frozenset(
              {"id", "client_id", "engagement_id", "observation_id", "reviewer_consultant_id",
               "decision", "reliability", "reviewed_statement", "review_number"}))
    check("classified append-only: no UPDATE grant is needed",
          rp.RUNTIME_TABLE_PERSISTENCE[TABLE] == rp.APPEND_ONLY)
    check("no allowlist entry writes discovery_observations from the review",
          not any(t == "discovery_observations" and "review" in a
                  for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS))
    src = read("peak/workspace/observation_reviews.py")
    check("the review service imports no model client and writes no other table",
          not re.search(r"anthropic|openai|peak\.agents|\bllm\b", src, re.I)
          and set(re.findall(r'_require_allowed\("(\w+)"', src)) == {TABLE}
          and "update(" not in src and "delete(" not in src)


# --------------------------------------------------------------------------- 2. the rule


def _summaries(outside, reviews=None):
    obs = [{"observation_id": "dobs_a", "session_id": "s1",
            "observation_text": "Receipts are keyed a day late.", "recorded_by_consultant_id": "c1",
            "basis": "observed", "category": "receiving"},
           {"observation_id": "dobs_b", "session_id": None if outside else "s1",
            "observation_text": "Cycle counts skip the overflow bay.",
            "recorded_by_consultant_id": "c2", "basis": "measured", "low_hanging_fruit": True,
            "estimated_effort": "low", "estimated_value": "high"}]
    out = {"north_star": {"engagement_id": "e1", "north_star": "Trustworthy on-hand"},
           "sessions": [{"session_id": "s1", "interviewee_name": "Dana", "status": "completed"}],
           "answers": [], "observations": obs, "active_questions": [],
           "consultant_names": {"c1": "Cam", "c2": "Lee"}}
    if reviews is not None:
        out["lead_reviews"] = reviews
    return out


def _review(n=1, decision="approve_internal", reliability="medium", observation="dobs_a",
            engagement="e1", statement="Receipts are keyed a day late.", reviewer="c1"):
    return {"review_id": f"olr_{observation}_{n}", "engagement_id": engagement,
            "observation_id": observation, "reviewer_consultant_id": reviewer,
            "decision": decision, "reliability": reliability, "reviewed_statement": statement,
            "review_number": n}


def rule_checks():
    print("\n[2. the rule: derived, deterministic, every control kept]")
    import dataclasses

    from peak.reports import discovery_assessment as da
    from peak.reports.final_report import compose_final_report, render_final_report_markdown
    from peak.reports.internal_assessment import (
        InternalAssessment, render_internal_assessment_markdown,
    )
    from peak.reports.packet_view import EvidenceView
    from peak.reports.packet_view_report import recommendation_block_reasons
    from peak.workspace.approvals import report_content_hash

    def eligibility(reviews, outside=False):
        ctx = da.build_discovery_assessment_context(_summaries(outside, reviews))
        return {e.finding_id: e for e in ctx.recommendation_eligibility}, ctx

    a = "disc_dobs_a"
    none, ctx = eligibility([])
    check("no Lead review: blocked, for that reason only",
          none[a].recommendation_blocked_reasons == [da.OBS_BLOCK_NO_LEAD_REVIEW]
          and not none[a].recommendation_eligible and none[a].lead_review is None)
    ok, _ = eligibility([_review()])
    check("an approval at medium, of the exact statement: eligible",
          ok[a].recommendation_eligible and ok[a].recommendation_blocked_reasons == [])
    check("an approval at high: eligible",
          eligibility([_review(reliability="high")])[0][a].recommendation_eligible)
    check("reliability low: blocked (the Phase 117 reliability control)",
          eligibility([_review(reliability="low")])[0][a].recommendation_blocked_reasons
          == [da.OBS_BLOCK_RELIABILITY_LOW])
    check("reliability missing or unrecognised: blocked",
          all(eligibility([_review(reliability=r)])[0][a].recommendation_blocked_reasons
              == [da.OBS_BLOCK_RELIABILITY_UNSPECIFIED] for r in (None, "certain")))
    check("a decline: blocked (an approving review is still required)",
          eligibility([_review(decision="decline", reliability=None)])[0][a]
          .recommendation_blocked_reasons == [da.OBS_BLOCK_NOT_APPROVED])
    check("the observation changed since review: blocked (the persisted statement control)",
          eligibility([_review(statement="Receipts are keyed late.")])[0][a]
          .recommendation_blocked_reasons == [da.OBS_BLOCK_STATEMENT_CHANGED])
    check("a review of another engagement or observation never counts (target-specific)",
          eligibility([_review(engagement="e2")])[0][a].recommendation_blocked_reasons
          == [da.OBS_BLOCK_NO_LEAD_REVIEW]
          and eligibility([_review(observation="dobs_b")])[0][a].recommendation_blocked_reasons
          == [da.OBS_BLOCK_NO_LEAD_REVIEW])
    later, _ = eligibility([_review(1), _review(2, decision="decline", reliability=None)])
    earlier, _ = eligibility([_review(2), _review(1, decision="decline", reliability=None)])
    check("the highest-numbered review is current, whatever the row order",
          not later[a].recommendation_eligible and earlier[a].recommendation_eligible
          and later[a].lead_review.review_number == 2)
    check("deterministic: the same records give the same decision",
          dataclasses.asdict(eligibility([_review()])[1])
          == dataclasses.asdict(eligibility([_review()])[1]))
    check("reviewed by its author is recorded, not refused",
          ok[a].reviewed_by_author is True
          and eligibility([_review(reviewer="c9")])[0][a].reviewed_by_author is False)
    fields = {f.name for f in dataclasses.fields(da.DiscoveryFinding)}
    check("the finding itself gains no field: no eligibility, review or reliability on it",
          not fields & {"recommendation_eligible", "review_status", "reliability", "lead_review",
                        "claim_scope"})

    def ev(**kw):
        base = dict(evidence_id="evid_1", linked_review_ids=["rev_1"],
                    effective_review_status="approved_internal", reliability="medium",
                    claim_scope="operational_finding", source_resolved=True,
                    finding_statement_persisted=True, schema_item={"summary": "S"})
        base.update(kw)
        return EvidenceView(**base)

    check("the Phase 117 evidence rule still requires each control",
          recommendation_block_reasons(ev()) == []
          and recommendation_block_reasons(ev(linked_review_ids=[]))
          and recommendation_block_reasons(ev(effective_review_status="reviewed_not_approved"))
          and recommendation_block_reasons(ev(reliability="low"))
          and recommendation_block_reasons(ev(claim_scope=None))
          and recommendation_block_reasons(ev(finding_statement_persisted=False))
          and recommendation_block_reasons(ev(schema_item={}))
          and recommendation_block_reasons(ev(source_resolved=False)))
    same = []
    for path in UNCHANGED:
        base = subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=REPO_ROOT,
                              capture_output=True, text=True)
        same.append(base.returncode == 0 and base.stdout == read(path))
    check("the evidence rule, recommendation, report, reader and approval modules are unchanged",
          all(same))

    for outside in (False, True):
        assessment = InternalAssessment(
            engagement_id="e1",
            discovery=da.build_discovery_assessment_context(_summaries(outside, [])))
        report = compose_final_report(assessment, {"id": "e1", "engagement_label": "L"})
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()[:16]  # noqa: E731
        got = (h(render_internal_assessment_markdown(assessment)),
               h(render_final_report_markdown(report)), report_content_hash(report)[:16])
        check(f"no Lead review ({'some outside interviews' if outside else 'interviews only'}): "
              f"assessment and report byte-identical to the baseline's", got == BASELINE_HASHES[outside])

    reviewed = InternalAssessment(engagement_id="e1", discovery=da.build_discovery_assessment_context(
        _summaries(True, [_review()])))
    unreviewed = InternalAssessment(engagement_id="e1", discovery=da.build_discovery_assessment_context(
        _summaries(True, [])))
    r1 = compose_final_report(reviewed, {"id": "e1", "engagement_label": "L"})
    r0 = compose_final_report(unreviewed, {"id": "e1", "engagement_label": "L"})
    check("a Lead review leaves the Final Report and its content hash unchanged",
          report_content_hash(r1) == report_content_hash(r0)
          and render_final_report_markdown(r1) == render_final_report_markdown(r0))
    md = render_internal_assessment_markdown(reviewed)
    check("the assessment shows the review and eligibility beside the finding, and drafts nothing",
          "- Lead review: approved for internal reliance, reliability medium, by Cam, who recorded it"
          in md and "- Recommendation eligibility: eligible" in md
          and "No recommendation is drafted from discovery material." in md
          and reviewed.recommendations == [] and reviewed.recommendation_status == "blocked")
    check("its discovery sentence no longer claims no reliability rating or eligibility",
          da.LEAD_REVIEWED_TAIL in md and "no reliability rating, and no recommendation" not in md)
    from peak.workspace.advisory_boundary import framing_violations
    check("the new wording crosses no advisory boundary",
          not framing_violations(da.LEAD_REVIEWED_TAIL)
          and not framing_violations("\n".join(l for l in md.splitlines() if "Lead review" in l)))


# --------------------------------------------------------------------------- 3-5. app


def app_checks(tmp):
    print("\n[3. authority]")
    app, factory, store, client, db = p220._setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    from peak import accounts
    accounts.create_consultant(factory, name="Ash Other", email="ash@example.com",
                               role="consultant", password=p220.PASSWORD)
    ash = client("ash")
    cam_id = cam.get("/auth/me").json()["consultant"]["id"]
    ash_id = ash.get("/auth/me").json()["consultant"]["id"]
    pid, phase = p220._phase(lee, "Alpha")
    eid = phase["engagement_id"]
    task = phase["tasks"][0]
    _, phase_b = p220._phase(lee, "Beta")
    eid_b = phase_b["engagement_id"]
    text = "Receipts are keyed a day late because the dock log is on paper."
    r = cam.post(f"/tasks/{task['id']}/observations", json={"observation_text": text, "basis": "observed"})
    assert r.status_code == 201, r.text
    oid = r.json()["observation"]["id"]
    r = cam.post(f"/engagements/{eid_b}/observations", json={"observation_text": "Beta note."})
    oid_b = r.json()["observation"]["id"]

    def state(c=cam, o=oid):
        return c.get(f"/observations/{o}/lead-review").json()["lead_review"]

    def post(body, c=cam, o=oid):
        return c.post(f"/observations/{o}/lead-review", json=body)

    def body(s, decision="approve_internal", reliability="medium", **kw):
        return {"decision": decision, "reliability": reliability,
                "statement_hash": s["statement_hash"],
                "current_review_id": s["history"][0]["review_id"] if s["history"] else None, **kw}

    def rows():
        return p220._counts(db).get("observation_lead_reviews")

    check("logged out, reading and reviewing return 401",
          anon.get(f"/observations/{oid}/lead-review").status_code == 401
          and anon.post(f"/observations/{oid}/lead-review", json={}).status_code == 401)
    s0 = state()
    check("before any review: blocked for no Lead review, no Lead assigned",
          s0["eligibility"]["recommendation_blocked_reasons"] == ["no Lead review of this observation"]
          and s0["lead"] is None and s0["you_are_lead"] is False and s0["history"] == [])
    r = post(body(s0))
    check("no Lead assigned: refused (no_lead_consultant), nothing written",
          r.status_code == 422 and code(r) == "no_lead_consultant" and rows() == 0)
    assert lee.patch(f"/engagements/{eid}", json={"assigned_consultant_id": cam_id}).status_code == 200
    assert lee.patch(f"/engagements/{eid_b}", json={"assigned_consultant_id": ash_id}).status_code == 200
    check("an Admin who is not the Lead is refused (not_lead_consultant)",
          code(post(body(s0), c=lee)) == "not_lead_consultant" and rows() == 0)
    check("another consultant is refused (not_lead_consultant)",
          code(post(body(s0), c=ash)) == "not_lead_consultant" and rows() == 0)
    sb = state(o=oid_b)
    check("cross-engagement: this engagement's Lead cannot review another engagement's observation",
          code(post(body(sb), o=oid_b)) == "not_lead_consultant" and rows() == 0)
    check("the Lead's page says they are the Lead; others' does not",
          state()["you_are_lead"] is True and state(c=ash)["you_are_lead"] is False
          and state(c=ash)["lead"]["id"] == cam_id)
    check("invalid requests are refused: approval without reliability, decline with one, extra field",
          post(body(s0, reliability=None)).status_code == 422
          and post(body(s0, decision="decline")).status_code == 422
          and post({**body(s0), "recommendation_text": "x"}).status_code == 422
          and post({**body(s0), "decision": "client_facing_approve"}).status_code == 422
          and rows() == 0)
    check("a stale text is refused (observation_changed)",
          code(post(body(s0, statement_hash="0" * 64))) == "observation_changed" and rows() == 0)
    check("a stale review is refused (review_changed)",
          code(post(body(s0, current_review_id="olr_x"))) == "review_changed" and rows() == 0)

    print("\n[4. the Lead's review, and what stays unchanged]")
    before = _snapshot(db)
    report_before = cam.get(f"/engagements/{eid}/final-report").json()
    pkg = lee.post(f"/engagements/{eid}/final-report/packages", json={})
    assert pkg.status_code == 201, pkg.text
    packages_before = lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]
    readiness_before = cam.get(f"/phases/{pid}/readiness").json()
    before = _snapshot(db)
    r = post(body(s0))
    s1 = r.json()["lead_review"]
    after = _snapshot(db)
    check("the Lead's approval is accepted: one row, numbered 1, eligible",
          r.status_code == 200 and rows() == 1 and s1["history"][0]["review_number"] == 1
          and s1["eligibility"]["recommendation_eligible"] is True
          and s1["eligibility"]["lead_review"]["reliability"] == "medium")
    check("only observation_lead_reviews changed: the observation, origins, evidence and review "
          "records, tasks, phases and artifacts did not",
          _changed(before, after) == {TABLE})
    import sqlite3
    con = sqlite3.connect(db)
    row = con.execute(f"SELECT reviewer_consultant_id, observation_id, engagement_id, decision, "
                      f"reliability, reviewed_statement, owner_id, authorization_scope FROM {TABLE}"
                      ).fetchone()
    con.close()
    check("provenance: reviewer, observation, engagement, decision, reliability and the exact text",
          row == (cam_id, oid, eid, "approve_internal", "medium", text, "peak_consultants",
                  "engagement_authorized"))
    check("the original observation reads exactly as before",
          cam.get(f"/observations/{oid}").json()["observation"]["observation_text"] == text)
    r2 = post(body(s1))
    r3 = post(body(s0))  # a double submit, still naming the review the Lead was first shown
    check("idempotent: repeating the current decision writes nothing",
          r2.status_code == 200 and r3.status_code == 200 and rows() == 1
          and _snapshot(db) == after)

    reads = _snapshot(db)
    a = cam.get(f"/engagements/{eid}/assessment").json()
    report_after = cam.get(f"/engagements/{eid}/final-report").json()
    cam.get(f"/observations/{oid}/lead-review")
    cam.get(f"/engagements/{eid}/final-report.docx")
    packages_after = lee.get(f"/engagements/{eid}/final-report/packages").json()["review"]
    check("reads write nothing", _snapshot(db) == reads)
    elig = a["assessment"]["discovery"]["recommendation_eligibility"]
    check("the assessment carries the derived eligibility beside the finding",
          len(elig) == 1 and elig[0]["recommendation_eligible"] is True
          and "recommendation_eligible" not in a["assessment"]["discovery"]["findings"][0])
    check("no recommendation is drafted and no evidence-backed finding appears",
          a["assessment"]["recommendations"] == [] and a["assessment"]["findings"] == []
          and a["assessment"]["recommendation_status"] == "blocked")
    check("the Final Report is unchanged: same content, no review, no eligibility",
          report_after == report_before and "Lead review" not in report_after["markdown"]
          and "recommendation_eligibility" not in str(report_after["report"]))
    check("the earlier package is unchanged and still matches the draft",
          packages_after["draft_matches_latest"] is True
          and packages_after["packages"] == packages_before["packages"])
    check("readiness, task and phase are unchanged",
          cam.get(f"/phases/{pid}/readiness").json() == readiness_before)

    print("\n[5. edits, declines and new reviews]")
    cam.patch(f"/observations/{oid}", json={"observation_text": text + " Since March."})
    s2 = state()
    check("an edit after review: blocked as changed, history kept, no review rewritten",
          s2["eligibility"]["recommendation_blocked_reasons"]
          == ["the observation has changed since the Lead reviewed it"]
          and s2["history"][0]["statement_matches"] is False and rows() == 1)
    check("a review naming the old text is refused", code(post(body(s1))) == "observation_changed")
    r = post(body(s2, reliability="high"))
    s3 = r.json()["lead_review"]
    check("the Lead reviews the new wording: review 2, eligible again",
          r.status_code == 200 and rows() == 2 and s3["history"][0]["review_number"] == 2
          and s3["eligibility"]["recommendation_eligible"] is True)
    r = post(body(s3, decision="decline", reliability=None))
    s4 = r.json()["lead_review"]
    check("a decline supersedes it: blocked, three reviews in history",
          s4["eligibility"]["recommendation_blocked_reasons"]
          == ["the current Lead review does not approve it for internal reliance"]
          and [h["review_number"] for h in s4["history"]] == [3, 2, 1])
    r = post(body(s4, reliability="low"))
    check("an approval rated low is recorded but blocked",
          r.json()["lead_review"]["eligibility"]["recommendation_blocked_reasons"]
          == ["the Lead rated its reliability low"])
    con = sqlite3.connect(db)
    governed = con.execute("SELECT (SELECT COUNT(*) FROM evidence_references) + "
                           "(SELECT COUNT(*) FROM review_records)").fetchone()[0]
    con.close()
    check("nothing is written to the governed evidence path", governed == 0)
    from peak.db.models import ObservationLeadReview
    with factory() as session:
        row = session.query(ObservationLeadReview).first()
        row.reliability = "high"
        try:
            session.commit()
            immutable = False
        except PermissionError:
            immutable = True
    check("a stored review cannot be updated", immutable)


# --------------------------------------------------------------------------- 6. static


def static_checks():
    print("\n[6. static UI]")
    panel = read(PANEL)
    check("the panel says what is reviewed and what it means",
          "exactly as it reads now" in panel and "internal" in panel and "reliability" in panel)
    check("the panel says it creates no recommendation and the Final Report does not change",
          "It does not create a" in panel and "the Final Report does not change" in panel)
    check("the panel says what still applies after an edit",
          "no longer applies until the Lead reviews it again" in panel)
    check("only the Lead sees the form; nothing is prefilled",
          "state.you_are_lead ?" in panel and "defaultChecked" not in panel
          and "defaultValue" not in panel)
    check("the page degrades before the API: no panel when the review cannot be read",
          "{review && (" in read(OBSERVATION_PAGE)
          and "if (!res.ok) return null;" in read("web/lib/api.ts"))
    check("no report, artifact or publication code reads Lead reviews",
          not any("lead_review" in read(p) or "ObservationLeadReview" in read(p)
                  for p in ("peak/reports/final_report.py", "peak/reports/release_presentation.py",
                            "peak/workspace/artifacts.py", "peak/workspace/approvals.py",
                            "web/components/final-report-view.tsx")))
    check("the Phase 226 target is in make validate",
          re.search(r"^validate: .*\bvalidate-phase226\b", read("Makefile"), re.M) is not None)


def main() -> int:
    print("Peak Phase 226 observation Lead review check")
    print("=" * 44)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase226_") as tmp:
        schema_checks(tmp)
        rule_checks()
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())

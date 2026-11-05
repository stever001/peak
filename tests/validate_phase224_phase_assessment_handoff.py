#!/usr/bin/env python3
"""Phase 224 — phase-to-assessment handoff (offline; temporary SQLite and a temporary local store only).

Proves:

1. **No schema or authority.** No migration, model, allowlist action, persistence classification or
   verifier-pin change. The handoff is composed; the origin's flag is derived.
2. **The problem, reproduced.** A fully documented, ready phase has put nothing in the assessment,
   and records and result summaries never reach it on their own.
3. **The narrowed rule.** A work observation is accepted on a resolved task and on any agreed task of
   a completed phase, by the signed-in consultant, in their words, with its origin. A planned phase,
   a suggested task, blank text, an interview, and another engagement's or a replaced capture are
   still refused, atomically.
4. **What stays frozen.** Records, captures, task progress and completion stay closed. Only
   observations, origins and links change; task, phase, readiness and the completion stamp do not.
5. **Provenance.** ``written_after_work`` is false during the work, true after it, derived, and
   survives an edit. The label stays truthful everywhere an origin is shown.
6. **Assessment and report.** An after-the-work observation is an ordinary discovery-derived finding,
   not recommendation-eligible. No recommendation, evidence-backed finding or artifact appears. No
   origin or task id enters the assessment or the Final Report.
7. **The derived handoff.** Counts and the task list follow the rows, stay scoped to the phase, are
   deterministic, and reading writes nothing.
8. **Static UI.** Touch-sized links, no form on the record, nothing prefilled, the degrade path, the
   advisory-boundary scan, and no report, artifact or publication code reads the handoff.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)
import validate_phase223_phase_work_record as p223  # noqa: E402  (shared fixtures)

HEAD = "025_observation_task_origins"
OBSERVATION_TABLES = {"discovery_observations", "observation_task_origins",
                      "observation_evidence_links"}
HANDOFF_UI = "web/components/assessment-handoff.tsx"
RECORD_PAGE = "web/app/(workspace)/phases/[id]/record/page.tsx"
PHASE_PAGE = "web/app/(workspace)/phases/[id]/page.tsx"
TASK_PAGE = "web/app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx"
DURING = "web/components/observed-during.tsx"
CARD = "web/components/discovery-section.tsx"
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


code, read = p220.code, p220.read
_snapshot, _strip_paths = p223._snapshot, p223._strip_paths


def _changed(before, after):
    return {t for t in after if before.get(t) != after[t]}


# --------------------------------------------------------------------------- 1. no schema


def schema_checks():
    print("\n[1. no schema change, no new authority]")
    from peak.persistence import allowlist, runtime_persistence as rp

    versions = [v for v in os.listdir(os.path.join(REPO_ROOT, "alembic", "versions"))
                if v.endswith(".py")]
    check("Phase 224 adds no migration (025 stays; the only later one is Phase 226's 026)",
          {v for v in versions if v[:3] > "025"} <= {"026_observation_lead_reviews.py"}
          and f"{HEAD}.py" in versions)
    check("the production verifier pin does not move",
          f'EXPECTED_ALEMBIC_HEAD = "{HEAD}"' in read("tools/production_mysql_collation_verify.py"))
    check("no model, table, policy or allowlist entry names a handoff",
          "handoff" not in read("peak/db/models.py").lower()
          and not any("handoff" in t for t in rp.RUNTIME_TABLE_PERSISTENCE)
          and not any("handoff" in t or "handoff" in a for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS))
    check("written_after_work is derived: no column and no allowlist entry",
          "written_after_work" not in read("peak/db/models.py")
          and "written_after_work" not in read("peak/persistence/allowlist.py"))
    check("the origin stays append-only, with the same one create action and six columns",
          rp.RUNTIME_TABLE_PERSISTENCE["observation_task_origins"] == rp.APPEND_ONLY
          and allowlist.WORKSPACE_WRITE_COLUMNS[("observation_task_origins",
                                                 "create_observation_task_origin")]
          == frozenset({"id", "client_id", "engagement_id", "observation_id", "phase_id", "task_id"}))
    src = read("peak/workspace/phase_work_record.py")
    check("the work record service still writes nothing",
          not re.search(r"session\.(add|delete|commit|merge|flush|execute\(\s*(update|delete|insert))"
                        r"|_require_allowed|\bupdate\(|\binsert\(", src))
    obs = read("peak/workspace/task_observations.py")
    check("the observation rule checks no role: no new authority",
          "actor_role" not in obs and "lead_or_admin" not in obs)
    check("no model, LLM or synthesis call in either service",
          not re.search(r"anthropic|openai|\bllm\b|synthes", src + obs, re.I))
    check("no other module updates a task or phase, so updated_at is its finishing time",
          not any(re.search(r"update\((PhaseTask|EngagementPhase)\b", read(os.path.join("peak", d, f)))
                  for d in ("workspace", "consultant_api", "reports")
                  for f in os.listdir(os.path.join(REPO_ROOT, "peak", d))
                  if f.endswith(".py") and f != "engagement_phases.py"))


# --------------------------------------------------------------------------- 2-7. app


def app_checks(tmp):
    print("\n[2. the problem: ready, complete, and nothing in the assessment]")
    from peak.workspace import engagement_phases, phase_work_record as pwr

    app, factory, store, client, db = p220._setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    lee_id = lee.get("/auth/me").json()["consultant"]["id"]
    pid, phase = p220._phase(lee, "Alpha")
    eid = phase["engagement_id"]
    t = {x["sequence"]: x for x in phase["tasks"]}
    pid_b, phase_b = p220._phase(lee, "Beta")
    eid_b, tid_b = phase_b["engagement_id"], phase_b["tasks"][0]["id"]
    pid_c, phase_c = p220._phase(lee, "Gamma", authorize=False)
    tid_c = phase_c["tasks"][0]["id"]

    def record(c=cam, phase_id=pid):
        return c.get(f"/phases/{phase_id}/work-record").json()["work_record"]

    def handoff(phase_id=pid):
        return record(phase_id=phase_id)["assessment_handoff"]

    def observe(text, task_id, c=cam, **extra):
        return c.post(f"/tasks/{task_id}/observations", json={"observation_text": text, **extra})

    def upload(task_id, caption, supersedes=None):
        grant = cam.get(f"/tasks/{task_id}/evidence").json()["task_evidence"]["upload"]["grant"]
        data = {"grant": grant, "caption": caption, "evidence_kind": "photo"}
        if supersedes:
            data["supersedes_evidence_id"] = supersedes
        r = anon.post("/evidence-uploads", data=data,
                      files={"file": ("IMG_7731.JPG", p220.JPEG, "image/jpeg")})
        assert r.status_code == 201, r.text
        return r.json()["evidence"]["id"]

    def assessment():
        return lee.get(f"/engagements/{eid}/assessment").json()

    def report():
        return lee.get(f"/engagements/{eid}/final-report").json()

    note = "A recurring keying delay, recorded as a task note."
    summary = "A result summary about receiving."
    cap = upload(t[1]["id"], "Receiving log")
    cap_old = upload(t[1]["id"], "Blurry")
    cap_new = upload(t[1]["id"], "Clear", supersedes=cap_old)
    cap_b = upload(tid_b, "Other engagement photo")

    empty = handoff()
    check("before any observation: none counted, and captured work without one is listed",
          empty["observations"] == 0 and empty["open"] is True
          and [x["sequence"] for x in empty["without_observation"]] == [1])
    for seq in (1, 2, 4, 6):
        cam.post(f"/tasks/{t[seq]['id']}/records", json={"record_kind": "note", "record_text": note})
        r = cam.post(f"/tasks/{t[seq]['id']}/completion", json={"result_summary": summary})
        assert r.status_code == 200, r.text
    cam.post(f"/tasks/{t[5]['id']}/not-applicable", json={"reason": "No camera today."})
    rec = record()
    a_empty, r_empty = assessment(), report()
    blob = json.dumps(a_empty["assessment"]) + json.dumps(r_empty)
    check("the phase is ready, with records and summaries on every required task",
          rec["readiness"]["ready"] is True and rec["totals"]["completed"] == 4
          and rec["totals"]["observations"] == 0)
    check("yet no finding exists: records and summaries do not reach the assessment or report",
          not (a_empty["assessment"]["discovery"] or {}).get("findings")
          and a_empty["assessment"]["findings"] == []
          and note not in blob and summary not in blob)
    h = handoff()
    check("the handoff says so: 0 observations, and each task with recorded work listed in order",
          h["observations"] == 0 and h["written_after_work"] == 0
          and [x["sequence"] for x in h["without_observation"]] == [1, 2, 4, 6])
    check("a task resolved not applicable, or whose condition was not met, has no recorded work",
          not any(x["sequence"] in (3, 5) for x in h["without_observation"]))
    check("the handoff does not block completion or change readiness",
          rec["readiness"]["blocking"] == [] and "assessment_handoff" not in rec["readiness"])

    print("\n[3. the narrowed rule]")
    before = _snapshot(db)
    a_before, r_before = assessment(), report()
    readiness_before = lee.get(f"/phases/{pid}").json()["phase"]["readiness"]
    time.sleep(1.1)  # timestamps have one-second resolution; "after" must be a later second
    resolved_text = "Keying runs a day behind because the log is on paper."
    r_resolved = observe(resolved_text, t[1]["id"], basis="inferred", evidence_ids=[cap])
    o_resolved = r_resolved.json()["observation"] if r_resolved.status_code == 201 else {}
    check("an observation is accepted on a completed task (201)", r_resolved.status_code == 201)
    check("it is in the consultant's words, by the signed-in consultant, in the task's engagement",
          o_resolved.get("observation_text") == resolved_text and o_resolved["basis"] == "inferred"
          and o_resolved["recorded_by"] == "Cam Consultant" and o_resolved["engagement_id"] == eid
          and o_resolved["session"] is None)
    check("its origin names the phase and task, and says it was written after the work",
          o_resolved["origin"]["phase_id"] == pid and o_resolved["origin"]["task_id"] == t[1]["id"]
          and o_resolved["origin"]["task_sequence"] == 1
          and o_resolved["origin"]["written_after_work"] is True)
    r_na = observe("The absence of a camera shapes how labels get checked.", t[5]["id"])
    r_cond = observe("Nothing mismatched, so nobody had to resolve anything.", t[3]["id"])
    check("also on a task resolved not applicable, and on one whose condition was not met",
          r_na.status_code == 201 and r_cond.status_code == 201)
    check("any signed-in consultant may write it, as in Phase 222; the Lead too",
          observe("Lead's own observation.", t[2]["id"], c=lee).status_code == 201)
    check("the task read no longer reports recording as closed",
          cam.get(f"/tasks/{t[1]['id']}/observations").json()["task_observations"]
          ["recording_closed"] is None)

    def blocked(response, expected):
        return code(response) == expected

    suggested = engagement_phases.add_task(factory, pid, {"title": "Count the returns cage",
                                                          "instructions": "Count it.",
                                                          "inclusion_reason": "Synthesis"},
                                           lee_id, origin="si_suggested")
    tid_s = next(x["id"] for x in suggested["tasks"] if x["status"] == "suggested")
    planned_before = _snapshot(db)
    check("logged out: 401", anon.post(f"/tasks/{t[1]['id']}/observations",
                                       json={"observation_text": "x"}).status_code == 401)
    check("an unknown task: 404", observe("x", "ptask_0000000000000000").status_code == 404)
    check("a planned phase stays refused (phase_not_authorized)",
          blocked(observe("Too early.", tid_c), "phase_not_authorized")
          and cam.get(f"/tasks/{tid_c}/observations").json()["task_observations"]
          ["recording_closed"]["code"] == "phase_not_authorized")
    check("a suggested task stays refused (task_not_accepted)",
          blocked(observe("Not agreed work.", tid_s), "task_not_accepted")
          and cam.get(f"/tasks/{tid_s}/observations").json()["task_observations"]
          ["recording_closed"]["code"] == "task_not_accepted")
    check("blank text stays refused; nothing fills it in",
          blocked(observe("   ", t[1]["id"]), "invalid_field"))
    check("another engagement's capture is refused",
          blocked(observe("Forged.", t[1]["id"], evidence_ids=[cap_b]), "invalid_link"))
    check("a replaced capture is refused",
          blocked(observe("Old photo.", t[1]["id"], evidence_ids=[cap_old]), "evidence_replaced"))
    check("naming an interview is refused",
          observe("Interview.", t[1]["id"], session_id="dses_x").status_code == 422)
    check("the refused saves wrote nothing, even with a valid capture listed first",
          blocked(observe("Atomic.", t[1]["id"], evidence_ids=[cap_new, cap_b]), "invalid_link")
          and _snapshot(db) == planned_before)

    print("\n[4. what stays frozen]")
    frozen_before = _snapshot(db)
    grant_closed = cam.get(f"/tasks/{t[1]['id']}/evidence").json()["task_evidence"]["upload"]
    check("a record on a resolved task stays refused (task_resolved)",
          code(cam.post(f"/tasks/{t[1]['id']}/records",
                        json={"record_kind": "note", "record_text": "Late."})) == "task_resolved")
    check("capture on a resolved task stays closed", grant_closed["available"] is False)
    check("completing or setting aside a resolved task stays refused",
          code(cam.post(f"/tasks/{t[1]['id']}/completion", json={"result_summary": "Again."}))
          == "task_resolved"
          and code(cam.post(f"/tasks/{t[1]['id']}/not-applicable", json={"reason": "Again."}))
          == "task_resolved"
          and code(cam.patch(f"/tasks/{t[1]['id']}", json={"consultant_notes": "Late."}))
          == "task_resolved")
    check("those refusals wrote nothing", _snapshot(db) == frozen_before)
    after_task = _snapshot(db)
    check("only observations, origins and links changed; task, phase, record and capture rows did not",
          _changed(before, after_task) <= OBSERVATION_TABLES | {"phase_tasks"}
          and not {"engagement_phases", "phase_task_records", "phase_task_evidence"}
          & _changed(before, after_task))
    phase_now = lee.get(f"/phases/{pid}").json()["phase"]
    check("readiness is unchanged by after-the-work observations",
          phase_now["readiness"]["ready"] == readiness_before["ready"]
          and phase_now["readiness"]["blocking"] == readiness_before["blocking"]
          and phase_now["readiness"]["required_resolved"] == readiness_before["required_resolved"])

    done = cam.post(f"/phases/{pid}/completion")
    closed_phase = done.json()["phase"]
    tasks_closed = {x["id"]: (x["status"], x["result_summary"], x["completed_at"])
                    for x in closed_phase["tasks"]}
    check("completing the phase is still possible and still requires only readiness",
          done.status_code == 200 and closed_phase["status"] == "completed")
    closed_before = _snapshot(db)
    time.sleep(1.1)
    after_phase_text = "Across the phase, the paper log is the common cause of keying delay."
    r_closed = observe(after_phase_text, t[6]["id"], evidence_ids=[cap_new])
    check("an observation is accepted after the phase is completed (201)",
          r_closed.status_code == 201)
    o_closed = r_closed.json()["observation"]
    check("it reads as written after the work", o_closed["origin"]["written_after_work"] is True)
    closed_after = _snapshot(db)
    check("by whole-database comparison, only observations, origins and links changed",
          _changed(closed_before, closed_after) == OBSERVATION_TABLES)
    phase_after = lee.get(f"/phases/{pid}").json()["phase"]
    check("the phase stays completed, with the same who and when",
          phase_after["status"] == "completed"
          and phase_after["completed_at"] == closed_phase["completed_at"]
          and phase_after["completed_by_consultant_id"] == closed_phase["completed_by_consultant_id"])
    check("no task changed: status, summary and completion time are as they were",
          {x["id"]: (x["status"], x["result_summary"], x["completed_at"])
           for x in phase_after["tasks"]} == tasks_closed)
    check("readiness is unchanged by it", phase_after["readiness"] == closed_phase["readiness"])
    check("records and captures stay refused on a completed phase (phase_closed)",
          code(cam.post(f"/tasks/{t[6]['id']}/records",
                        json={"record_kind": "note", "record_text": "Late."})) == "phase_closed"
          and cam.get(f"/tasks/{t[6]['id']}/evidence").json()["task_evidence"]["upload"]
          ["available"] is False)
    check("a completed phase cannot be completed again",
          code(cam.post(f"/phases/{pid}/completion")) == "phase_closed")

    print("\n[5. provenance]")
    pid_d, phase_d = p220._phase(lee, "Delta")
    t_d = {x["sequence"]: x for x in phase_d["tasks"]}
    r_d = observe("Seen on the dock while watching a delivery.", t_d[1]["id"])
    o_d = r_d.json()["observation"]
    check("during the work, written_after_work is false", o_d["origin"]["written_after_work"] is False)
    cam.post(f"/tasks/{t_d[1]['id']}/records", json={"record_kind": "note", "record_text": "x"})
    time.sleep(1.1)
    cam.post(f"/tasks/{t_d[1]['id']}/completion", json={"result_summary": "Done."})
    read_back = cam.get(f"/observations/{o_d['id']}").json()["observation"]
    check("finishing the task later does not relabel it: it was still observed during the work",
          read_back["origin"]["written_after_work"] is False)
    edited = cam.patch(f"/observations/{o_resolved['id']}", json={"observation_text": "Edited text."})
    check("an edit keeps the origin and the flag",
          edited.status_code == 200 and edited.json()["observation"]["origin"]
          == cam.get(f"/observations/{o_resolved['id']}").json()["observation"]["origin"]
          and edited.json()["observation"]["origin"]["written_after_work"] is True)
    cam.patch(f"/observations/{o_resolved['id']}", json={"observation_text": resolved_text})
    moved = cam.patch(f"/observations/{o_resolved['id']}", json={"task_id": t[2]["id"]})
    check("the origin still cannot be moved", moved.status_code == 422)
    from peak.db.models import ObservationTaskOrigin

    denied = False
    try:
        with factory() as s:
            row = s.query(ObservationTaskOrigin).filter_by(observation_id=o_resolved["id"]).one()
            row.task_id = t[2]["id"]
            s.commit()
    except PermissionError:
        denied = True
    check("the origin stays immutable under the ORM", denied)

    print("\n[6. assessment and report]")
    a_after, r_after = assessment(), report()
    findings = {f["trace"]["observation_id"]: f for f in a_after["assessment"]["discovery"]["findings"]}
    plain = cam.post(f"/engagements/{eid}/observations",
                     json={"observation_text": "Engagement-level note."}).json()["observation"]
    a_plain = assessment()
    plain_finding = next(f for f in a_plain["assessment"]["discovery"]["findings"]
                         if f["trace"]["observation_id"] == plain["id"])
    check("it becomes a discovery-derived finding quoting the consultant's text, shaped like any other",
          findings[o_closed["id"]]["statement"].startswith(after_phase_text)
          and findings[o_resolved["id"]]["statement"].startswith(resolved_text)
          and set(findings[o_closed["id"]]) == set(plain_finding))
    check("no finding quotes a record or result summary; only observations became findings",
          note not in json.dumps(a_after["assessment"]) and summary not in json.dumps(a_after["assessment"])
          and len(findings) == 5)
    check("it is not recommendation-eligible",
          not any(f.get("recommendation_eligible") for f in findings.values()))
    check("the evidence-backed findings and recommendations are unchanged",
          a_after["assessment"]["findings"] == a_before["assessment"]["findings"]
          and a_after["assessment"].get("recommendations") == a_before["assessment"].get("recommendations"))
    check("the Final Report's recommendations are unchanged, and it carries the observation's text",
          r_after.get("report", {}).get("recommendations") == r_before.get("report", {}).get("recommendations")
          and after_phase_text in json.dumps(r_after))
    check("the origin stays beside the assessment: no flag or task id inside it or the report",
          a_after["observation_origins"][o_closed["id"]]["written_after_work"] is True
          and "written_after_work" not in json.dumps(a_after["assessment"])
          and "written_after_work" not in json.dumps(r_after)
          and t[6]["id"] not in json.dumps(a_after["assessment"])
          and t[6]["id"] not in json.dumps(r_after))
    counts = p220._counts(db)
    check("no artifact, version, approval or release was created",
          all(counts[n] == 0 for n in counts if n.startswith("artifact")))
    check("no roadmap item, evidence reference or review record was created",
          counts["roadmap_items"] == 0 and counts.get("evidence_references", 0) == 0
          and counts.get("review_records", 0) == 0)

    print("\n[7. the derived handoff]")
    h = handoff()
    check("the counts follow the rows; the engagement-level observation is not counted",
          h["observations"] == 5 and plain["id"] not in json.dumps(h))
    check("four were written after the work; task 3's was not, as it was still open in an open phase",
          h["written_after_work"] == 4
          and [o["origin"]["written_after_work"] for x in record()["tasks"] if x["sequence"] == 3
               for o in x["observations"]] == [False])
    check("tasks with an observation leave the list; only task 4 remains",
          [x["sequence"] for x in h["without_observation"]] == [4])
    h_d = handoff(pid_d)
    check("the handoff is scoped: another phase counts only its own",
          h_d["observations"] == 1 and h_d["written_after_work"] == 0
          and h_d["without_observation"] == [])
    h_b = handoff(pid_b)
    check("another engagement's capture lists only its own task",
          [x["task_id"] for x in h_b["without_observation"]] == [tid_b]
          and eid not in json.dumps(h_b))
    h_c = handoff(pid_c)
    check("a planned phase is not open, and lists nothing",
          h_c["open"] is False and h_c["without_observation"] == [] and h_c["observations"] == 0)
    check("a suggested task is never listed",
          "Count the returns cage" not in json.dumps(handoff()))
    check("it says it is composed: not stored, not interpreted, and names what reaches the assessment",
          h["stored"] is False and h["interpreted"] is False
          and "Only observations reach the internal assessment" in h["rule"]
          and "no task needs one" in h["rule"])
    reads = _snapshot(db)
    direct = [pwr.phase_work_record(factory, pid) for _ in range(2)]
    check("two reads compose the same handoff; the service is deterministic",
          direct[0] == direct[1] and direct[0]["assessment_handoff"] == handoff())
    for _ in range(3):
        handoff()
        cam.get(f"/tasks/{t[1]['id']}/observations")
        assessment()
    check("reading the handoff, the task and the assessment changes no row in any table",
          _snapshot(db) == reads)
    check("the record route still accepts no write method",
          all(getattr(cam, m)(f"/phases/{pid}/work-record").status_code == 405
              for m in ("post", "put", "patch", "delete")))

    import sqlite3
    con = sqlite3.connect(db)
    secrets_ = [r[0] for r in con.execute("SELECT storage_key FROM phase_task_evidence")]
    secrets_ += [r[0] for r in con.execute("SELECT file_name FROM phase_task_evidence") if r[0]]
    secrets_ += [r[0] for r in con.execute("SELECT content_hash FROM phase_task_evidence")]
    con.close()
    bodies = [r_closed.text, r_resolved.text, json.dumps(record()), json.dumps(a_after)]
    check("no response carries a storage key, device file name or hash",
          secrets_ and not any(x in b for x in secrets_ for b in bodies))


# --------------------------------------------------------------------------- 8. static


def static_checks():
    print("\n[8. static UI checks]")
    ui, record_page, phase_page, task_page = (read(HANDOFF_UI), read(RECORD_PAGE), read(PHASE_PAGE),
                                              read(TASK_PAGE))
    check("the work record gains the section and stays free of any form or action",
          "<AssessmentHandoffSection" in record_page and "<form" not in record_page
          and "action=" not in record_page and "<form" not in ui and "action=" not in ui)
    check("the phase workspace shows the note only when the API provides it, not for a planned phase",
          "{handoff && <AssessmentHandoffNote" in phase_page
          and 'p.status === "planned" ? null' in phase_page)
    check("the note says observations can still be written after completion, and blocks nothing",
          "can still be written after this phase is completed" in ui
          and "disabled" not in phase_page)
    links = re.findall(r"<Link\b[^>]*?className=\"([^\"]*)\"", ui, re.S)
    check("every new link is touch-sized", links and all("min-h-touch" in c for c in links))
    check("the record's Write an observation link goes to the task page's section",
          "?observe=1#observations" in ui and "?observe=1#observations" in record_page
          and 'id="observations"' in task_page)
    check("the task form still follows the API: closed when recording_closed says so",
          "obs && !obs.recording_closed" in task_page)
    check("a finished task keeps its form collapsed unless the consultant asked for it",
          'search.observe === "1" || (!finished && obs.observations.length === 0)' in task_page)
    check("record and capture forms still need open work: nothing else on the task page opened up",
          "{workable && w.applies !== false && (\n              <div id=\"record-form\"" in task_page
          and "workable && w.applies !== false" in task_page
          and "const workable = authorized && isOpen(t);" in task_page)
    during, card = read(DURING), read(CARD)
    check("the label stays truthful: Observed during, or Written after the work on",
          "Written after the work on:" in during and "Observed during:" in during
          and "origin.written_after_work ?" in during
          and "Written after the work" in card and "written_after_work" in card)
    check("the field is optional in the web types, so an API before Phase 224 degrades",
          "written_after_work?: boolean" in read("web/lib/api.ts")
          and "assessment_handoff?: AssessmentHandoff" in read("web/lib/api.ts")
          and "handoff?.open" in record_page)
    check("no text is prefilled or derived from a record, caption or summary",
          not re.search(r"record_text|result_summary|caption|observation_text", ui)
          and "defaultValue" not in ui)
    check("no id is rendered as text",
          not re.search(r"(?<![=$])\{[\w.]*\.(id|task_id)\}", ui))
    from peak.workspace import advisory_boundary as b

    texts = p220._visible_text([ui, during, read("peak/workspace/phase_work_record.py")])
    texts += re.findall(r'"([^"\n]{20,})"', task_page[task_page.index("Phase 222"):][:900])
    hits = {x for x in texts if b.framing_violations(x)}
    hits |= {x for x in texts if re.search(r"\b(audit\w*|complian\w*|certif\w*|attest\w*|score\w*"
                                           r"|pass(ed)?|fail(ed)?|sign-?off|approv\w*)\b", x, re.I)}
    check("no audit, compliance, scoring or approval language in the new text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    check("no report, workflow, artifact or AgentNet code reads the handoff",
          not any("assessment_handoff" in read(os.path.join(d, f))
                  or "written_after_work" in read(os.path.join(d, f))
                  for d in ("peak/reports", "peak/workflows", "peak/agentnet", "peak/db")
                  for f in os.listdir(os.path.join(REPO_ROOT, d)) if f.endswith(".py"))
          and "assessment_handoff" not in read("peak/workspace/artifacts.py")
          and "assessment_handoff" not in read("peak/workspace/approvals.py"))
    check("the Final Report view does not show it",
          "written_after_work" not in read("web/components/final-report-view.tsx")
          and "AssessmentHandoff" not in read("web/components/final-report-view.tsx"))
    app_src = read("peak/consultant_api/app.py")
    check("no new route: the API file does not mention the handoff",
          "handoff" not in app_src.lower())
    makefile = read("Makefile")
    check("the harness is in make validate",
          "validate-phase224:" in makefile
          and re.search(r"^validate:.*validate-phase224", makefile, re.M) is not None)
    check("docs/PHASE224_PHASE_ASSESSMENT_HANDOFF.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE224_PHASE_ASSESSMENT_HANDOFF.md")))


def main() -> int:
    print("Peak Phase 224 phase-to-assessment handoff check")
    print("=" * 49)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    schema_checks()
    with tempfile.TemporaryDirectory(prefix="peak_phase224_") as tmp:
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())

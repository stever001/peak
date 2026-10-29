#!/usr/bin/env python3
"""Phase 221 — evidence referencing (offline; temporary SQLite and a temporary local store only).

Proves:

1. **Migration 024.** Upgrade from 023 creates exactly ``observation_evidence_links``; its columns
   match the model; a pair is linked at most once (UNIQUE); downgrade removes it; the migration
   carries no data and alters no existing table.
2. **Persistence policy.** The table is append-only; the allowlist has a single create action; the
   ORM refuses update and delete, singly and in bulk.
3. **Linking.** An observation with no evidence; one linked at creation; several; links added on
   edit by the signed-in consultant; a duplicate (repeated or already linked), a capture of another
   engagement, an unknown capture and a replaced capture are refused, and a refused save writes
   nothing (no observation, no link).
4. **Supersession.** A linked capture replaced later stays linked, marked replaced, and the newer
   capture is not put in its place; it is offered for new links instead.
5. **Assessment traceability.** The assessment response carries each observation's links (count,
   caption, originating task, a content path that serves the original bytes), outside the
   assessment itself.
6. **No leaks.** No response carries a storage key or device file name.
7. **Boundary.** Linking changes only the link table. The assessment, its findings and
   recommendations, the Final Report, task status and phase readiness are identical before and
   after; reading links changes nothing.
8. **Static UI checks.** The picker posts ``evidence_ids`` only when chosen; the pages degrade when
   linking is unavailable; no generated wording, storage key or audit language in the new UI.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sqlite3
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(REPO_ROOT, "tests")
for p in (REPO_ROOT, TESTS):
    if p not in sys.path:
        sys.path.insert(0, p)

import validate_phase220_guided_evidence_capture as p220  # noqa: E402  (shared fixtures)

TABLE = "observation_evidence_links"
UI_FILES = (
    "web/components/evidence-picker.tsx",
    "web/components/linked-evidence.tsx",
    "web/components/observation-form.tsx",
    "web/components/discovery-section.tsx",
    "web/components/assessment-view.tsx",
    "web/app/discovery-actions.ts",
    "web/app/(workspace)/engagements/[id]/page.tsx",
    "web/app/(workspace)/engagements/[id]/assessment/page.tsx",
    "web/app/(workspace)/observations/[id]/edit/page.tsx",
)
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


code, read, alembic = p220.code, p220.read, p220.alembic


# --------------------------------------------------------------------------- 1. migration


def migration_checks(tmp):
    print("\n[1. migration 024]")
    import sqlalchemy as sa

    import peak.db.models as m

    db = os.path.join(tmp, "mig.sqlite3")

    def inspector():
        return sa.inspect(sa.create_engine(f"sqlite:///{db}"))

    alembic(db, "upgrade", "023_phase_task_evidence").check_returncode()
    before = set(inspector().get_table_names())
    up = alembic(db, "upgrade", "024_observation_evidence_links")
    check("upgrade to 024 creates exactly observation_evidence_links",
          up.returncode == 0 and set(inspector().get_table_names()) - before == {TABLE})
    check("024 is the single head", alembic(db, "heads").stdout.split()[0]
          == "024_observation_evidence_links")
    migrated = {c["name"] for c in inspector().get_columns(TABLE)}
    check("the migrated columns match the model",
          migrated == set(m.Base.metadata.tables[TABLE].columns.keys()))
    check("the model is registered in ALL_MODELS", TABLE in {t.__tablename__ for t in m.ALL_MODELS})
    con = sqlite3.connect(db)
    sql = ("INSERT INTO observation_evidence_links (id, client_id, engagement_id, observation_id,"
           " evidence_id, linked_by_consultant_id, review_status, lifecycle_status)"
           " VALUES (?, 'c', 'e', ?, ?, 'x', 'draft', 'draft')")
    con.execute(sql, ("l1", "o1", "v1"))
    con.execute(sql, ("l2", "o1", "v2"))
    con.execute(sql, ("l3", "o2", "v1"))
    try:
        con.execute(sql, ("l4", "o1", "v1"))
        dup_refused = False
    except sqlite3.IntegrityError:
        dup_refused = True
    con.rollback()
    con.close()
    check("UNIQUE(observation, evidence) refuses a repeated pair; other pairs are fine", dup_refused)
    down = alembic(db, "downgrade", "023_phase_task_evidence")
    check("downgrade to 023 removes exactly that table",
          down.returncode == 0 and set(inspector().get_table_names()) == before)
    body = read("alembic/versions/024_observation_evidence_links.py").split('"""', 2)[2].lower()
    check("migration 024 carries no data and alters no existing table",
          "insert" not in body and "op.execute" not in body and "add_column" not in body
          and "alter_column" not in body and body.count("create_table") == 1)


# --------------------------------------------------------------------------- 2. policy


def policy_checks(tmp):
    print("\n[2. persistence policy]")
    from peak.db.models import ObservationEvidenceLink
    from peak.db.session import create_session_factory
    from peak.persistence import allowlist, runtime_persistence as rp

    check("observation_evidence_links is append-only (no UPDATE grant needed)",
          rp.RUNTIME_TABLE_PERSISTENCE.get(TABLE) == rp.APPEND_ONLY)
    actions = [a for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS if t == TABLE]
    check("the allowlist has one create action and nothing else",
          actions == ["create_observation_evidence_link"])
    db = os.path.join(tmp, "orm.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")
    with factory() as s:
        s.add(ObservationEvidenceLink(id="oevl_x", client_id="c", engagement_id="e",
                                      observation_id="o", evidence_id="v",
                                      linked_by_consultant_id="x"))
        s.commit()
    refused = []
    for attempt in ("update", "delete", "bulk_update", "bulk_delete"):
        with factory() as s:
            row = s.get(ObservationEvidenceLink, "oevl_x")
            try:
                if attempt == "update":
                    row.evidence_id = "other"
                    s.commit()
                elif attempt == "delete":
                    s.delete(row)
                    s.commit()
                else:
                    import sqlalchemy as sa
                    stmt = (sa.update(ObservationEvidenceLink).values(evidence_id="z")
                            if attempt == "bulk_update" else sa.delete(ObservationEvidenceLink))
                    s.execute(stmt)
                    s.commit()
            except PermissionError:
                refused.append(attempt)
    check("the ORM refuses update and delete, singly and in bulk",
          refused == ["update", "delete", "bulk_update", "bulk_delete"])


# --------------------------------------------------------------------------- 3-7. app


def app_checks(tmp):
    print("\n[3-7. linking, supersession, assessment, leaks, boundary]")
    app, factory, store, client, db = p220._setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    cam_name = "Cam Consultant"
    pid, phase = p220._phase(lee, "Alpha")
    task = next(t for t in phase["tasks"] if t["requires_record"])
    tid, eid = task["id"], phase["engagement_id"]
    pid_b, phase_b = p220._phase(lee, "Beta")
    tid_b, eid_b = phase_b["tasks"][0]["id"], phase_b["engagement_id"]

    def upload(task_id, caption, supersedes=None, name="IMG_7781.JPG", content=p220.JPEG):
        grant = cam.get(f"/tasks/{task_id}/evidence").json()["task_evidence"]["upload"]["grant"]
        data = {"grant": grant, "caption": caption,
                **({"supersedes_evidence_id": supersedes} if supersedes else {})}
        r = anon.post("/evidence-uploads", data=data, files={"file": (name, content, "image/jpeg")})
        assert r.status_code == 201, r.text
        return r.json()["evidence"]["id"]

    e1 = upload(tid, "Receiving log, dock 3")
    e2 = upload(tid, "Pallet label without a location")
    e3 = upload(tid, "Count sheet, aisle 4")
    e_b = upload(tid_b, "Other engagement photo")

    def observe(text, ids=None, c=cam):
        body = {"observation_text": text, **({"evidence_ids": ids} if ids is not None else {})}
        return c.post(f"/engagements/{eid}/observations", json=body)

    def links():
        return cam.get(f"/engagements/{eid}/evidence").json()["engagement_evidence"]

    check("logged out, an engagement's evidence returns 401",
          anon.get(f"/engagements/{eid}/evidence").status_code == 401)
    check("an unknown engagement's evidence returns 404",
          cam.get("/engagements/eng_unknown/evidence").status_code == 404)
    first = links()
    check("all current captures of the engagement are offered, with caption, task and date, "
          "and no capture of another engagement",
          {i["id"] for i in first["available"]} == {e1, e2, e3}
          and all(i["task"]["title"] == task["title"] and i["task"]["phase_id"] == pid
                  and i["created_at"] and i["caption"] and i["content_path"] for i in first["available"])
          and first["links"] == {})

    # Snapshot the derived views before any link, after the observations exist.
    o_none = observe("Receiving is logged on paper and keyed later.").json()["observation"]
    o_later = observe("Labels on received pallets do not carry a location.").json()["observation"]
    assess_before = lee.get(f"/engagements/{eid}/assessment").json()
    report_before = lee.get(f"/engagements/{eid}/final-report").json()
    phase_before = lee.get(f"/phases/{pid}").json()["phase"]
    counts_before = p220._counts(db)

    check("an observation with no evidence has no links",
          o_none["id"] not in links()["links"]
          and assess_before["observation_evidence"] == {})

    r_one = observe("The receiving log is not reconciled to the system.", [e1])
    o_one = r_one.json()["observation"]
    r_many = observe("Count sheets and pallet labels disagree on location.", [e2, e3])
    o_many = r_many.json()["observation"]
    got = links()["links"]
    check("an observation created with one capture links exactly it",
          r_one.status_code == 201 and [i["id"] for i in got.get(o_one["id"], [])] == [e1])
    check("an observation created with several captures links them all",
          r_many.status_code == 201 and sorted(i["id"] for i in got.get(o_many["id"], []))
          == sorted([e2, e3]))
    check("the observation text is exactly what the consultant wrote",
          o_one["observation_text"] == "The receiving log is not reconciled to the system."
          and o_many["observation_text"] == "Count sheets and pallet labels disagree on location.")
    r_add = cam.patch(f"/observations/{o_later['id']}", json={"evidence_ids": [e2]})
    later = links()["links"].get(o_later["id"], [])
    check("links can be added on edit (evidence only), linked by the signed-in consultant",
          r_add.status_code == 200 and [i["id"] for i in later] == [e2]
          and later[0]["linked_by"] == cam_name and later[0]["linked_at"])
    check("the same capture may support more than one observation",
          e2 in [i["id"] for i in links()["links"][o_many["id"]]] and later[0]["id"] == e2)

    # Refusals, and a refused save writes nothing.
    rows_before = p220._counts(db)
    r_dup = cam.patch(f"/observations/{o_one['id']}", json={"evidence_ids": [e1]})
    r_twice = observe("Twice chosen.", [e2, e2])
    r_cross = observe("Cross engagement.", [e1, e_b])
    r_unknown = observe("Unknown capture.", ["ptevd_0000000000000000"])
    r_cross_edit = cam.patch(f"/observations/{o_none['id']}",
                             json={"observation_text": "Changed?", "evidence_ids": [e_b]})
    check("an already-linked capture is refused (duplicate_link)", code(r_dup) == "duplicate_link")
    check("the same capture chosen twice is refused (duplicate_link)",
          code(r_twice) == "duplicate_link")
    check("a capture of another engagement, or an unknown one, is refused (invalid_link)",
          code(r_cross) == "invalid_link" and code(r_unknown) == "invalid_link"
          and code(r_cross_edit) == "invalid_link")
    check("a refused save writes nothing: no observation, no link, no edit",
          p220._counts(db) == rows_before
          and cam.get(f"/observations/{o_none['id']}").json()["observation"]["observation_text"]
          == o_none["observation_text"])
    check("an observation of another engagement cannot be given this engagement's capture",
          code(cam.post(f"/engagements/{eid_b}/observations",
                        json={"observation_text": "B side.", "evidence_ids": [e1]}))
          == "invalid_link")

    # Boundary: compare the derived views before and after linking.
    assess_after = lee.get(f"/engagements/{eid}/assessment").json()
    report_after = lee.get(f"/engagements/{eid}/final-report").json()
    phase_after = lee.get(f"/phases/{pid}").json()["phase"]
    counts_after = p220._counts(db)
    changed = {t for t in counts_after if counts_after[t] != counts_before.get(t)}
    check("linking changed only observation_evidence_links (plus the two new observations)",
          changed == {TABLE, "discovery_observations"}
          and counts_after["discovery_observations"] - counts_before["discovery_observations"] == 2)

    a_before, a_after = assess_before["assessment"], assess_after["assessment"]
    later_before = next(f for f in a_before["discovery"]["findings"]
                        if f["trace"]["observation_id"] == o_later["id"])
    later_after = next(f for f in a_after["discovery"]["findings"]
                       if f["trace"]["observation_id"] == o_later["id"])
    check("a linked observation's finding is unchanged by its links",
          later_before == later_after)
    check("evidence-backed findings, recommendations and readiness inputs are unchanged",
          all(a_before.get(k) == a_after.get(k) for k in a_before
              if k not in ("discovery", "generated_at", "created_at")))
    check("linked captures appear nowhere inside the assessment or the Final Report",
          not any(i in json.dumps(a_after) or i in json.dumps(report_after)
                  for i in (e1, e2, e3)))
    check("task status and phase readiness are unchanged",
          phase_after["readiness"] == phase_before["readiness"]
          and [t["status"] for t in phase_after["tasks"]]
          == [t["status"] for t in phase_before["tasks"]])
    check("the Final Report's recommendation material is unchanged",
          json.dumps(report_before.get("report", {}).get("recommendations"), sort_keys=True)
          == json.dumps(report_after.get("report", {}).get("recommendations"), sort_keys=True))

    # Assessment traceability.
    oe = assess_after["observation_evidence"]
    content = anon.get(oe[o_one["id"]][0]["content_path"])
    check("the assessment shows each linked observation's captures: count, caption, task",
          len(oe.get(o_one["id"], [])) == 1 and len(oe.get(o_many["id"], [])) == 2
          and oe[o_one["id"]][0]["caption"] == "Receiving log, dock 3"
          and all(i["task"]["title"] == task["title"] for i in oe[o_many["id"]])
          and o_none["id"] not in oe)
    check("a linked capture opens securely: its content path serves the original bytes",
          content.status_code == 200 and content.content == p220.JPEG
          and content.headers.get("x-content-type-options") == "nosniff")
    reads = p220._counts(db)
    links()
    lee.get(f"/engagements/{eid}/assessment")
    check("reading links and the assessment changes no table", p220._counts(db) == reads)

    # Supersession.
    e1_new = upload(tid, "Receiving log, dock 3 (retaken)", supersedes=e1)
    after_replace = links()
    kept = after_replace["links"][o_one["id"]]
    check("a replaced capture stays linked to the observation, marked replaced",
          [i["id"] for i in kept] == [e1] and kept[0]["superseded"] is True
          and kept[0]["superseded_by"] == e1_new)
    check("the newer capture is not put in its place",
          all(e1_new not in [i["id"] for i in v] for v in after_replace["links"].values()))
    check("the newer capture is offered for new links; the replaced one is not",
          e1_new in {i["id"] for i in after_replace["available"]}
          and e1 not in {i["id"] for i in after_replace["available"]})
    check("linking a replaced capture is refused (evidence_replaced)",
          code(cam.patch(f"/observations/{o_none['id']}", json={"evidence_ids": [e1]}))
          == "evidence_replaced")
    oe2 = lee.get(f"/engagements/{eid}/assessment").json()["observation_evidence"]
    check("the assessment still shows the historical capture, labelled replaced",
          oe2[o_one["id"]][0]["id"] == e1 and oe2[o_one["id"]][0]["superseded"] is True)

    # No leaks.
    con = sqlite3.connect(db)
    secrets_ = [r[0] for r in con.execute("SELECT storage_key FROM phase_task_evidence")]
    secrets_ += [r[0] for r in con.execute("SELECT file_name FROM phase_task_evidence") if r[0]]
    con.close()
    bodies = [json.dumps(links()), json.dumps(lee.get(f"/engagements/{eid}/assessment").json()),
              r_one.text, r_add.text]
    check("no response carries a storage key or device file name",
          secrets_ and not any(s in b for s in secrets_ for b in bodies)
          and not any(k in b for b in bodies for k in ('"storage_key"', '"file_name"')))


# --------------------------------------------------------------------------- 8. static


def static_checks():
    print("\n[8. static UI checks]")
    check("the UI files exist", all(os.path.exists(os.path.join(REPO_ROOT, p)) for p in UI_FILES))
    ui = {p: read(p) for p in UI_FILES}
    picker = ui["web/components/evidence-picker.tsx"]
    check("the picker is checkboxes named evidence_ids and leaves out captures already linked",
          'type="checkbox" name="evidence_ids"' in picker and "linkedIds.includes" in picker)
    actions = ui["web/app/discovery-actions.ts"]
    check("evidence_ids are sent only when chosen (an API before 221 is never sent them)",
          'getAll("evidence_ids")' in actions and "ids.length > 0 ? { evidence_ids: ids } : {}"
          in actions)
    api = read("web/lib/api.ts")
    check("getEngagementEvidence returns null (never notFound) when linking is unavailable",
          re.search(r"export async function getEngagementEvidence.{0,400}?\}\s*catch \{\s*return null;",
                    api, re.S) is not None and "if (!res.ok) return null;" in api)
    check("the pages degrade when linking is unavailable",
          "evidence={ev && {" in ui["web/app/(workspace)/engagements/[id]/page.tsx"]
          and "ev ? {" in ui["web/app/(workspace)/observations/[id]/edit/page.tsx"]
          and "observation_evidence ? {" in
          ui["web/app/(workspace)/engagements/[id]/assessment/page.tsx"])
    linked = ui["web/components/linked-evidence.tsx"]
    check("a replaced capture is labelled, and each item opens full size and names its task",
          "Replaced on its task since it was linked" in linked and "Open full size" in linked
          and "e.task.title" in linked)
    check("the new UI never handles a storage key, file name or bucket",
          not any(re.search(r"storage_key|file_name|bucket|PEAK_EVIDENCE_", s) for s in ui.values()))
    check("no generated wording: the observation text is never filled from evidence",
          not re.search(r"observation_text[^\n]*caption|caption[^\n]*observation_text",
                        "\n".join(ui.values())))
    from peak.workspace import advisory_boundary as b

    new_text = [read("web/components/evidence-picker.tsx"), linked]
    hits = {t for t in p220._visible_text(new_text) if b.framing_violations(t)}
    check("no audit / compliance / deficiency language in the new UI text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    service = read("peak/workspace/observation_evidence.py")
    check("the service never reads image content, and never imports the report or finding code",
          not re.search(r"^\s*(import|from)\s+(PIL|exif|pytesseract|cv2|piexif)", service, re.M)
          and "peak.reports" not in service and "peak.workflows" not in service)
    check("no route removes or edits a link",
          not re.search(r"@app\.(delete|patch|put)\([^)]*evidence-link", read(
              "peak/consultant_api/app.py")))
    check("docs/PHASE221_EVIDENCE_REFERENCING.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE221_EVIDENCE_REFERENCING.md")))


def main() -> int:
    print("Peak Phase 221 evidence referencing check")
    print("=" * 42)
    try:
        import argon2, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase221_") as tmp:
        migration_checks(tmp)
        policy_checks(tmp)
        app_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Phase 215 internal test engagements check (offline; temporary SQLite only).

An internal_test engagement is for testing, training and acceptance. Proves, through the
authenticated API:

1. a Consultant can create an internal_test engagement (under an internal test client), and becomes
   its Lead automatically; a Consultant cannot name another Lead or reassign afterwards;
2. an Admin can create one too;
3. it is stamped internal_test, real_client_data false, client_accessible false, with the workspace
   stamp and no capsule publication authority, and the classification cannot be spoofed;
4. it works through discovery, assessment, Final Report, DOCX, artifact version and release package;
5. one human may give both approvals on an internal_test package;
6. the same human is still refused on a real_client package, and other real-client controls are
   unchanged;
7. both approval stages are still required on an internal_test package;
8. an Admin can delete an internal_test engagement — logically: it is retired, every record is kept;
9. a Consultant cannot delete it;
10. a real_client engagement cannot be deleted through this path;
11. the source classification and status are machine-readable for future capsule projection;
12. no AgentNet / capsule publication is introduced.

And the creation UX contract:
- engagement creation offers Real Client and Internal Test / Training;
- Internal Test / Training needs the explicit confirmation (`internal_test_confirmed`), refused
  without it;
- its client chooser lists only reserved `internal_test_` clients;
- an existing engagement's classification cannot be switched;
- internal_test stays visibly identified.

Plus migration 020, the refusal of a historical internal record without the workspace stamp, and
that a deleted engagement accepts no new work. No network, no credential, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
PASSWORD = "synthetic-password-215"
SECRET = "synthetic-secret-215-" + "x" * 32
ARTIFACT_TABLES = ("artifacts", "artifact_versions", "artifact_release_packages",
                   "artifact_renditions", "artifact_approvals",
                   "artifact_final_approver_designations", "artifact_releases")


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def alembic(env, *args):
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True)


def _env(db):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    return env


def migration_checks(tmp):
    print("\n[migration 020]")
    import sqlalchemy as sa

    db = os.path.join(tmp, "mig.sqlite3")

    def columns():
        return {c["name"] for c in sa.inspect(sa.create_engine(f"sqlite:///{db}"))
                .get_columns("engagements")}

    up = alembic(_env(db), "upgrade", "020_internal_test_engagement_retirement")
    check("upgrade to 020 adds engagements.deleted_at and deleted_by_consultant_id",
          up.returncode == 0 and {"deleted_at", "deleted_by_consultant_id"} <= columns())
    down = alembic(_env(db), "downgrade", "019_artifact_approval_release")
    check("downgrade to 019 removes exactly those two columns",
          down.returncode == 0 and not {"deleted_at", "deleted_by_consultant_id"} & columns())
    src = open(os.path.join(REPO_ROOT,
                            "alembic/versions/020_internal_test_engagement_retirement.py")).read()
    body = src.split('"""', 2)[2].lower()
    targets = set(re.findall(r'op\.\w+\("(\w+)"', body)) | set(re.findall(r'table_name="(\w+)"', body))
    check("migration 020 carries no data and changes only the engagements table",
          "insert" not in body and "op.execute" not in body and targets == {"engagements"})


def build(tmp):
    db = os.path.join(tmp, "app.sqlite3")
    alembic(_env(db), "upgrade", "head").check_returncode()
    from peak.db.session import create_session_factory

    factory = create_session_factory(url=f"sqlite:///{db}")
    import init_discovery_questions as init

    init.initialize(factory)
    return factory


def code(response):
    detail = response.json().get("detail") if response.status_code >= 400 else None
    return detail.get("code") if isinstance(detail, dict) else response.status_code


def main_checks(factory):
    from fastapi.testclient import TestClient
    from sqlalchemy import func, select

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db import models
    from peak.persistence import allowlist

    people = {}
    for key, name, role in (("ada", "Ada Admin", "admin"), ("lee", "Lee Lead", "consultant"),
                            ("fran", "Fran Final", "consultant")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True)
    c = {}
    for key in people:
        c[key] = TestClient(app, base_url="https://testserver")
        c[key].post("/auth/login", json={"email": f"{key}@example.com", "password": PASSWORD})
    ada, lee, fran = c["ada"], c["lee"], c["fran"]

    def row(eid):
        with factory() as s:
            return s.get(models.Engagement, eid)

    def counts():
        with factory() as s:
            return {t: s.scalar(select(func.count()).select_from(m.__table__))
                    for t, m in ((m.__tablename__, m) for m in models.ALL_MODELS)
                    if t in ARTIFACT_TABLES + ("discovery_sessions", "discovery_answers",
                                               "discovery_observations", "engagements")}

    def act(who, pid, path, **body):
        return who.post(f"/release-packages/{pid}/{path}", json=body)

    def decide(who, pid, level, h, reviewed="web"):
        return act(who, pid, level, decision="approved", package_hash=h, reviewed_rendition=reviewed)

    # --- 1-3. creation and stamping -------------------------------------------------------------
    print("\n[1-3. Admin and Consultant create internal test records; classification is forced]")
    r = lee.post("/clients", json={"organization_label": "Synthetic Test Co (Lee)",
                                   "internal_test": True})
    lee_client = r.json().get("client", {})
    check("a Consultant can create an internal test client in the reserved namespace",
          r.status_code == 201 and lee_client["id"].startswith("internal_test_")
          and lee_client["internal_test"] is True)
    r = ada.post("/clients", json={"organization_label": "Peak Internal Acceptance (synthetic)",
                                   "internal_test": True})
    test_client = r.json()["client"]
    check("an Admin can create an internal test client in the reserved namespace",
          r.status_code == 201 and test_client["id"].startswith("internal_test_"))
    real_client = lee.post("/clients", json={"organization_label": "Synthetic Real Co"}
                           ).json()["client"]
    check("an ordinary client is unchanged (not internal test)",
          real_client["id"].startswith("client_") and real_client["internal_test"] is False)
    r = lee.post("/clients", json={"organization_label": "Spoof Co", "id": "internal_test_spoof"})
    check("a caller cannot choose a client id (422)", r.status_code == 422)

    print("\n[the Internal Test client chooser lists only reserved internal test clients]")
    only_test = {c["id"] for c in lee.get("/clients", params={"internal_test": "true"}).json()["clients"]}
    only_real = {c["id"] for c in lee.get("/clients", params={"internal_test": "false"}).json()["clients"]}
    everyone = {c["id"] for c in lee.get("/clients").json()["clients"]}
    check("?internal_test=true lists exactly the internal_test_ clients",
          only_test == {lee_client["id"], test_client["id"]}
          and all(i.startswith("internal_test_") for i in only_test))
    check("?internal_test=false lists only real clients; no filter lists both",
          only_real == {real_client["id"]} and everyone == only_test | only_real)

    body = {"client_id": test_client["id"], "engagement_label": "Internal Acceptance 215",
            "current_phase": "Assessment", "internal_test": True, "internal_test_confirmed": True}

    print("\n[4. Internal Test / Training needs the explicit confirmation]")
    for missing in ({"internal_test_confirmed": None}, {"internal_test_confirmed": False}):
        r = lee.post("/engagements", json={**body, **missing})
        check(f"internal_test without confirmation ({missing}) is refused",
              r.status_code == 422 and code(r) == "internal_test_confirmation_required")
    r = ada.post("/engagements", json={**body, "internal_test_confirmed": None})
    check("an Admin also needs the confirmation",
          r.status_code == 422 and code(r) == "internal_test_confirmation_required")
    r = lee.post("/engagements", json={"client_id": real_client["id"], "engagement_label": "Confirm only",
                                       "internal_test_confirmed": True})
    check("the confirmation alone never makes an engagement internal_test",
          r.status_code == 201 and row(r.json()["engagement"]["id"]).engagement_category == "real_client")
    r = lee.post("/engagements", json={**body, "client_id": lee_client["id"],
                                       "engagement_label": "Lee Internal 215"})
    lee_eid = r.json().get("engagement", {}).get("id")
    check("1. a Consultant can create an internal_test engagement", r.status_code == 201)
    le = row(lee_eid) if lee_eid else None
    check("   and it is stamped internal_test, real_client_data false, client_accessible false",
          le is not None and le.engagement_category == "internal_test"
          and le.real_client_data is False and le.client_accessible is False)

    print("\n[3. the classification is server-forced and cannot be spoofed]")
    spoofs = [{"engagement_category": "real_client"}, {"real_client_data": True},
              {"client_accessible": True}, {"capsule_publication_authorized": True},
              {"owner_id": "peak_internal_admin"}, {"authorization_scope": "internal_peak_only"},
              {"deleted_at": "2026-01-01T00:00:00"}]
    check("sending any classification, governance or retirement column is refused (422)",
          all(lee.post("/engagements", json={**body, **x}).status_code == 422 for x in spoofs))
    r = lee.post("/engagements", json={**body, "internal_test": None})
    check("a real_client engagement under an internal test client is refused",
          r.status_code == 422 and code(r) == "classification_mismatch")
    r = lee.post("/engagements", json={**body, "internal_test": False})
    check("internal_test: false cannot downgrade an internal test client's engagement",
          r.status_code == 422 and code(r) == "classification_mismatch")
    r = lee.post("/engagements", json={**body, "client_id": real_client["id"]})
    check("an internal_test engagement under a real client is refused",
          r.status_code == 422 and code(r) == "classification_mismatch")
    print("\n[6. an existing engagement's classification cannot be switched]")
    switches = [{"engagement_category": "real_client"}, {"internal_test": False},
                {"internal_test": True, "internal_test_confirmed": True}, {"client_accessible": True},
                {"real_client_data": True}, {"client_id": real_client["id"]}]
    check("no edit switches internal_test to real_client (422, row unchanged)",
          all(lee.patch(f"/engagements/{lee_eid}", json=x).status_code == 422 for x in switches)
          and row(lee_eid).engagement_category == "internal_test"
          and row(lee_eid).client_id == lee_client["id"])

    r = ada.post("/engagements", json={**body, "assigned_consultant_id": people["ada"]})
    eng = r.json()["engagement"]
    eid = eng["id"]
    check("2. an Admin can create an internal_test engagement", r.status_code == 201)
    e = row(eid)
    check("stamped internal_test, real_client_data false, client_accessible false",
          e.engagement_category == "internal_test" and e.real_client_data is False
          and e.client_accessible is False)
    check("it carries the workspace stamp and no capsule publication authority",
          all(getattr(e, k) == v for k, v in allowlist.WORKSPACE_ENGAGEMENT_CREATION_STAMP.items())
          and e.capsule_publication_authorized is False)
    check("the classification columns stay forbidden to every workspace write",
          set(allowlist.WORKSPACE_INTERNAL_TEST_CLASSIFICATION)
          <= allowlist.WORKSPACE_FORBIDDEN_COLUMNS)

    print("\n[1/3. real_client creation and real-client controls are unchanged]")
    r = lee.post("/engagements", json={"client_id": real_client["id"], "engagement_label": "Lee Real",
                                       "assigned_consultant_id": people["lee"]})
    check("a Consultant still cannot assign the Lead on create (403)",
          r.status_code == 403 and code(r) == "admin_required")
    r = lee.post("/engagements", json={"client_id": real_client["id"], "engagement_label": "Lee Real"})
    lr = row(r.json()["engagement"]["id"]) if r.status_code == 201 else None
    check("a Consultant still creates a real_client engagement, born real_client and client-accessible",
          lr is not None and lr.engagement_category == "real_client"
          and lr.real_client_data is True and lr.client_accessible is True)

    print("\n[Lead assignment on internal_test]")
    check("1. a Consultant-created internal_test engagement has its creator as Lead (server-set)",
          row(lee_eid).assigned_consultant_id == people["lee"]
          and lee.get(f"/engagements/{lee_eid}").json()["engagement"]["assigned_consultant"]["id"]
          == people["lee"])
    r = lee.post("/engagements", json={**body, "client_id": lee_client["id"],
                                       "engagement_label": "Lee names Fran",
                                       "assigned_consultant_id": people["fran"]})
    check("2. a Consultant cannot assign anyone else on create (403)",
          r.status_code == 403 and code(r) == "admin_required")
    reassign = [lee.patch(f"/engagements/{lee_eid}", json={"assigned_consultant_id": x})
                for x in (people["fran"], people["ada"], None)]
    check("3. a Consultant cannot reassign the Lead afterwards (403, unchanged)",
          all(x.status_code == 403 and code(x) == "admin_required" for x in reassign)
          and row(lee_eid).assigned_consultant_id == people["lee"])
    r = ada.post("/engagements", json={**body, "client_id": lee_client["id"],
                                       "engagement_label": "Ada assigns Fran",
                                       "assigned_consultant_id": people["fran"]})
    check("4. an Admin creates internal_test and assigns a Lead",
          r.status_code == 201 and row(r.json()["engagement"]["id"]).assigned_consultant_id
          == people["fran"])
    r = ada.post("/engagements", json={**body, "client_id": lee_client["id"],
                                       "engagement_label": "Ada unassigned"})
    check("   or leaves it unassigned", r.status_code == 201
          and row(r.json()["engagement"]["id"]).assigned_consultant_id is None)
    check("   and an Admin can still reassign an internal_test Lead",
          ada.patch(f"/engagements/{r.json()['engagement']['id']}",
                    json={"assigned_consultant_id": people["lee"]}).status_code == 200)
    r = lee.patch(f"/engagements/{lr.id}", json={"assigned_consultant_id": people["lee"]})
    check("5. a Consultant still cannot assign a real_client Lead afterwards (403)",
          r.status_code == 403 and code(r) == "admin_required" and row(lr.id).assigned_consultant_id is None)
    r = ada.post("/engagements", json={"client_id": real_client["id"], "engagement_label": "Ada Real"})
    check("3. an Admin can create a real_client engagement too",
          r.status_code == 201 and row(r.json()["engagement"]["id"]).engagement_category == "real_client")
    real_id = lr.id
    check("no edit switches real_client to internal_test (422, row unchanged)",
          all(lee.patch(f"/engagements/{real_id}", json=x).status_code == 422
              for x in ({"engagement_category": "internal_test"}, {"internal_test": True,
                        "internal_test_confirmed": True}, {"client_id": lee_client["id"]}))
          and row(real_id).engagement_category == "real_client")

    print("\n[7. internal_test stays visibly identified]")
    listed = {x["id"]: x for x in lee.get("/engagements").json()["engagements"]}
    check("the engagement list and detail mark it engagement_classification internal_test",
          listed[lee_eid]["engagement_classification"] == "internal_test"
          and lee.get(f"/engagements/{lee_eid}").json()["engagement"]["engagement_classification"]
          == "internal_test"
          and listed[real_id]["engagement_classification"] == "real_client")
    web = lambda rel: open(os.path.join(REPO_ROOT, "web", rel)).read()  # noqa: E731
    badged = ["components/engagement-list.tsx", "app/(workspace)/engagements/[id]/page.tsx",
              "app/(workspace)/engagements/[id]/final-report/page.tsx",
              "components/artifact-review-panel.tsx", "app/(workspace)/clients/page.tsx",
              "app/(workspace)/clients/[id]/page.tsx", "components/engagement-form.tsx"]
    check("the Internal Test badge is shown on the list, engagement, report, review, client and form "
          "surfaces", all("InternalTestBadge" in web(f) for f in badged))
    form = web("components/engagement-form.tsx")
    check("the form offers Real Client and Internal Test / Training, an internal-test-client chooser, a "
          "create link and the required confirmation",
          '"Real Client"' in form and '"Internal Test / Training"' in form
          and "/clients/new?internal_test=1" in form and 'name="internal_test_confirmed"' in form
          and "will not be client-accessible" in form
          and "/clients?internal_test=true" in web("app/(workspace)/engagements/new/page.tsx"))

    # --- 4. workflow ------------------------------------------------------------------------------
    print("\n[4. the normal discovery/report/artifact workflow accepts internal_test]")
    ok = ada.patch(f"/engagements/{eid}/north-star",
                   json={"north_star": "Synthetic: faster cycle counts"}).status_code == 200
    sess = ada.post(f"/engagements/{eid}/sessions", json={"interviewee_name": "Synthetic Person"})
    obs = ada.post(f"/engagements/{eid}/observations",
                   json={"observation_text": "Synthetic: counts lag by two days."})
    check("discovery: North Star, interview and observation recorded",
          ok and sess.status_code == 201 and obs.status_code == 201)
    check("assessment, Final Report and the draft DOCX load",
          ada.get(f"/engagements/{eid}/assessment").status_code == 200
          and ada.get(f"/engagements/{eid}/final-report").status_code == 200
          and ada.get(f"/engagements/{eid}/final-report.docx").status_code == 200)
    r = ada.post(f"/engagements/{eid}/final-report/packages")
    p = r.json()["package"]
    web = ada.get(f"/release-packages/{p['id']}/web")
    docx = ada.get(f"/release-packages/{p['id']}/docx")
    check("an artifact version and a release package with stored web and DOCX renditions",
          r.status_code == 201 and p["artifact_version_id"] and web.status_code == 200
          and docx.status_code == 200 and set(p["renditions"]) == {"web", "docx"})
    check("the renditions carry no Internal Test label (the label is UI chrome only)",
          b"Internal Test" not in web.content and b"internal_test" not in web.content)

    # --- 7. both stages still required ---------------------------------------------------------
    print("\n[7. both approval stages are still required for internal_test]")
    h = p["package_hash"]
    r = act(ada, p["id"], "final-approver", consultant_id=people["ada"])
    check("no Final Approver designation before the Lead approval",
          r.status_code == 422 and code(r) == "lead_approval_required")
    r = decide(ada, p["id"], "final-approval", h)
    check("no final approval before the Lead approval",
          r.status_code == 422 and code(r) == "lead_approval_required")
    check("the Lead (Ada) approves, recording the reviewed rendition",
          decide(ada, p["id"], "lead-approval", h, reviewed="docx").status_code == 200)
    r = decide(ada, p["id"], "final-approval", h)
    check("no final approval before a Final Approver is designated",
          r.status_code == 422 and code(r) == "no_final_approver_designated")
    r = act(ada, p["id"], "release", package_hash=h)
    check("no release before the final approval",
          r.status_code == 422 and code(r) == "approvals_required")

    # --- 5. same human permitted -----------------------------------------------------------------
    print("\n[5. one human may give both approvals on an internal_test package]")
    r = act(ada, p["id"], "final-approver", consultant_id=people["ada"])
    check("the Lead designates themselves as Final Approver", r.status_code == 200)
    r = decide(ada, p["id"], "final-approval", h)
    check("and gives the final approval, bound to the same package hash",
          r.status_code == 200 and r.json()["package"]["final_decision"]["package_hash"] == h
          and r.json()["package"]["lead_decision"]["package_hash"] == h)
    r = act(ada, p["id"], "release", package_hash=h)
    released = r.json()["package"] if r.status_code == 200 else {}
    check("and releases it", r.status_code == 200 and released.get("state") == "released")
    check("the released web is the stored bytes",
          ada.get(f"/release-packages/{p['id']}/web").content == web.content)

    # --- 6. real_client keeps the rule ------------------------------------------------------------
    print("\n[6. real_client still refuses the same human]")
    rid = ada.post("/engagements", json={"client_id": real_client["id"],
                                         "engagement_label": "Real 215", "current_phase": "Assessment",
                                         "assigned_consultant_id": people["lee"]}
                   ).json()["engagement"]["id"]
    re_row = row(rid)
    check("a real_client engagement is born real_client / client_accessible",
          re_row.engagement_category == "real_client" and re_row.client_accessible is True)
    lee.patch(f"/engagements/{rid}/north-star", json={"north_star": "Synthetic real North Star"})
    lee.post(f"/engagements/{rid}/observations", json={"observation_text": "Synthetic note."})
    rp = lee.post(f"/engagements/{rid}/final-report/packages").json()["package"]
    decide(lee, rp["id"], "lead-approval", rp["package_hash"])
    r = act(lee, rp["id"], "final-approver", consultant_id=people["lee"])
    check("the Lead cannot designate themselves (same_human)",
          r.status_code == 422 and code(r) == "same_human")
    check("a different consultant can still be designated",
          act(lee, rp["id"], "final-approver", consultant_id=people["fran"]).status_code == 200)

    print("\n[6. same-human two-stage approval end-to-end on the Consultant-created engagement]")
    lee.patch(f"/engagements/{lee_eid}/north-star", json={"north_star": "Synthetic practice goal"})
    lee.post(f"/engagements/{lee_eid}/observations", json={"observation_text": "Synthetic practice note."})
    lp = lee.post(f"/engagements/{lee_eid}/final-report/packages").json()["package"]
    lh = lp["package_hash"]
    steps = [decide(lee, lp["id"], "lead-approval", lh, reviewed="web"),
             act(lee, lp["id"], "final-approver", consultant_id=people["lee"]),
             decide(lee, lp["id"], "final-approval", lh, reviewed="docx"),
             act(lee, lp["id"], "release", package_hash=lh)]
    done = steps[-1].json().get("package", {}) if steps[-1].status_code == 200 else {}
    check("Lee (Consultant, auto-assigned Lead) approves, self-designates, final-approves and releases",
          all(x.status_code == 200 for x in steps) and done.get("state") == "released")
    check("both decisions are Lee's, bound to the same package hash, with their reviewed renditions",
          done["lead_decision"]["by"]["id"] == done["final_decision"]["by"]["id"] == people["lee"]
          and done["lead_decision"]["package_hash"] == done["final_decision"]["package_hash"] == lh
          and (done["lead_decision"]["reviewed_rendition"], done["final_decision"]["reviewed_rendition"])
          == ("web", "docx"))

    # --- 11 / 12. source marker, no publication -----------------------------------------------
    print("\n[11-12. machine-readable source state; no publication]")
    got = ada.get(f"/engagements/{eid}").json()["engagement"]
    check("11. the engagement reports engagement_classification internal_test, source_status active",
          got["engagement_classification"] == "internal_test" and got["source_status"] == "active")
    check("the package carries the same source marker",
          released.get("source") == {"engagement_classification": "internal_test",
                                     "source_status": "active"})
    with factory() as s:
        published = (s.scalar(select(func.count()).select_from(models.CapsulePublicationCandidate))
                     + s.scalar(select(func.count()).select_from(models.ResolverCapsuleRecord)))
    routes = [getattr(rt, "path", "") for rt in app.routes]
    check("12. no capsule record was written and no route publishes",
          published == 0 and not any("publish" in r_ or "capsule" in r_ for r_ in routes))

    # --- historical internal record -------------------------------------------------------------
    print("\n[a historical internal record without the workspace stamp stays refused]")
    with factory() as s:
        s.add(models.Engagement(id="eng_anchor_215", client_id="internal_test_anchor",
                                engagement_label="Anchor", owner_id="peak_internal_admin",
                                authorization_scope="internal_peak_only",
                                engagement_category="internal_test", real_client_data=False,
                                client_accessible=False))
        s.commit()
    r = ada.post("/engagements/eng_anchor_215/observations", json={"observation_text": "x"})
    check("discovery refuses it (not_a_workspace_engagement)",
          r.status_code == 422 and code(r) == "not_a_workspace_engagement")
    r = ada.post("/engagements/eng_anchor_215/final-report/packages")
    check("packaging refuses it", r.status_code in (404, 422))

    # --- 8-10. logical deletion -----------------------------------------------------------------
    print("\n[8-10. an Admin deletes internal_test logically; nothing else can delete]")
    path = f"/engagements/{eid}/internal-test-deletion"
    confirm = {"confirm_engagement_label": "Internal Acceptance 215"}
    r = lee.post(path, json=confirm)
    check("9. a Consultant cannot delete it (403)", r.status_code == 403)
    r = ada.post(f"/engagements/{rid}/internal-test-deletion",
                 json={"confirm_engagement_label": "Real 215"})
    check("10. a real_client engagement cannot be deleted (not_internal_test)",
          r.status_code == 422 and code(r) == "not_internal_test" and row(rid).deleted_at is None)
    r = ada.post(path, json={"confirm_engagement_label": "wrong"})
    check("the Admin must repeat the engagement name exactly",
          r.status_code == 422 and code(r) == "confirmation_required" and row(eid).deleted_at is None)
    before = counts()
    r = ada.post(path, json=confirm)
    after = counts()
    e = row(eid)
    check("8. an Admin deletes it: deleted_at and the deleting Admin are recorded",
          r.status_code == 200 and e.deleted_at is not None
          and e.deleted_by_consultant_id == people["ada"])
    check("nothing is physically deleted: engagement, discovery and artifact rows all kept",
          before == after and all(after[t] > 0 for t in ARTIFACT_TABLES))
    check("it leaves the engagement list and its client's list",
          eid not in {x["id"] for x in ada.get("/engagements").json()["engagements"]}
          and not ada.get(f"/clients/{test_client['id']}").json()["client"]["engagements"])
    got = ada.get(f"/engagements/{eid}").json()["engagement"]
    check("it stays readable for audit, with source_status deleted",
          got["source_status"] == "deleted" and got["engagement_classification"] == "internal_test")
    check("its released package stays readable and unchanged",
          ada.get(f"/release-packages/{p['id']}/web").content == web.content
          and ada.get(f"/release-packages/{p['id']}").json()["package"]["source"]["source_status"]
          == "deleted")
    refusals = [
        ada.post(f"/engagements/{eid}/observations", json={"observation_text": "late"}),
        ada.patch(f"/engagements/{eid}/north-star", json={"north_star": "late"}),
        ada.post(f"/engagements/{eid}/final-report/packages"),
        ada.patch(f"/engagements/{eid}", json={"current_phase": "late"}),
        ada.patch(f"/sessions/{sess.json()['session']['id']}", json={"notes": "late"}),
        ada.patch(f"/observations/{obs.json()['observation']['id']}",
                  json={"observation_text": "late"}),
        act(ada, p["id"], "final-approver", consultant_id=people["fran"]),
        ada.post(path, json=confirm),
    ]
    check("a deleted engagement accepts no new discovery, report, package, approval or edit",
          all(x.status_code == 422 and code(x) == "engagement_deleted" for x in refusals))
    check("no new row appeared after those refusals", counts() == after)
    check("the retirement action never names a physical delete",
          ("engagements", "retire_internal_test_engagement") in allowlist.WORKSPACE_WRITE_COLUMNS
          and not allowlist.is_prohibited_action("retire_internal_test_engagement"))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        migration_checks(tmp)
        main_checks(build(tmp))
    print("\n========================================================")
    print("Summary")
    print(f"  failures : {len(_failures)}")
    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())

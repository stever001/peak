#!/usr/bin/env python3
"""Phase 220 — guided evidence capture (offline; temporary SQLite and a temporary local store only).

Proves:

1. **Migration 023.** Upgrade from 022 creates exactly ``phase_task_evidence``; its columns match
   the model; the CHECK constraints refuse values outside each vocabulary; downgrade removes it;
   the migration carries no data and alters no existing table.
2. **Persistence policy.** The table is append-only (no UPDATE grant needed, Phase 50 gate
   unchanged); the allowlist has a single create action; the ORM refuses update and delete.
3. **Storage boundary.** The local store refuses traversal keys and overwrites, and has no delete
   or listing; a filesystem store is never configured against a MySQL runtime database. The R2
   adapter (stubbed, no network) writes conditionally so an existing key is refused, maps errors
   without detail, fails closed on an incomplete configuration with no fallback, and logs variable
   names only.
4. **API.** Logged-out reads get 401; the upload grant authenticates the upload (forged and expired
   grants refused); type is decided from the bytes (a renamed GIF is refused, a JPEG declared as
   PNG is stored as JPEG); empty and oversize files refused; linking only to a current record of the
   same task; supersession once only; hash and server-generated key recorded; listings never expose
   the key or file name; content served unchanged with safe headers through a short-lived token;
   a tampered stored file is refused; capture closed for a planned phase and a resolved task; no
   route removes or edits evidence; capture off when no store is configured.
5. **Optional on the task page.** ``getTaskEvidence`` (run under Node against stubbed responses)
   returns the evidence when the API has it, the clean unavailable state when storage is off, and
   null (never notFound() or an error) when the route is absent, failing or unreachable; it makes
   one GET; the API's listing changes no table; ``apiGet`` keeps its 404 behaviour.
6. **Boundary.** An upload changes no other table: no observation, finding, recommendation,
   governed assessment evidence, task record or artifact; task status and phase readiness are
   unchanged; evidence does not satisfy a task's record requirement.
7. **Static UI checks.** The form posts straight to the API as multipart with the grant; accepted
   types match the API; the camera is offered, not forced; no storage key in the web app; the
   advisory-boundary text scan passes; Phase 218 files still carry no file input.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

WEB = os.path.join(REPO_ROOT, "web")
PASSWORD = "phase220-password"
SECRET = "phase220-secret-key-phase220-secret-key"
WEB_BASE = "https://web.example"
TABLE = "phase_task_evidence"
UI_FILES = (
    "web/lib/evidence.ts",
    "web/components/evidence-capture.tsx",
    "web/components/evidence-list.tsx",
    "web/app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx",
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(range(256)) * 8
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + bytes(64)
HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + bytes(64)
_failures = []


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def alembic(db, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True)


def code(response):
    detail = response.json().get("detail") if response.status_code >= 400 else None
    return detail.get("code") if isinstance(detail, dict) else response.status_code


def read(path):
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- 1. migration


def migration_checks(tmp):
    print("\n[1. migration 023]")
    import sqlalchemy as sa

    import peak.db.models as m

    db = os.path.join(tmp, "mig.sqlite3")

    def inspector():
        return sa.inspect(sa.create_engine(f"sqlite:///{db}"))

    alembic(db, "upgrade", "022_engagement_roadmap_work_plan").check_returncode()
    before = set(inspector().get_table_names())
    up = alembic(db, "upgrade", "023_phase_task_evidence")
    check("upgrade to 023 creates exactly phase_task_evidence",
          up.returncode == 0 and set(inspector().get_table_names()) - before == {TABLE})
    migrated = {c["name"] for c in inspector().get_columns(TABLE)}
    check("the migrated columns match the model",
          migrated == set(m.Base.metadata.tables[TABLE].columns.keys()))
    check("the model is registered in ALL_MODELS",
          TABLE in {t.__tablename__ for t in m.ALL_MODELS})
    con = sqlite3.connect(db)
    good = ("'c', 'e', 'p', 't', {kind}, {media}, 10, 'h', {backend}, {key}, 'x', 'draft', 'draft'")
    sql = ("INSERT INTO phase_task_evidence (id, client_id, engagement_id, phase_id, task_id,"
           " evidence_kind, media_type, byte_length, content_hash, storage_backend, storage_key,"
           " uploaded_by_consultant_id, review_status, lifecycle_status) VALUES ({id}, " + good + ")")
    base = {"kind": "'photo'", "media": "'image/jpeg'", "backend": "'filesystem'"}
    bad = []
    for i, override in enumerate(({"kind": "'finding'"}, {"media": "'application/pdf'"},
                                  {"backend": "'public_url'"})):
        try:
            con.execute(sql.format(id=f"'b{i}'", key=f"'k{i}'", **{**base, **override}))
            bad.append(override)
        except sqlite3.IntegrityError:
            pass
    try:
        con.execute(sql.format(id="'z'", key="'kz'", **base).replace(", 10, ", ", 0, "))
        bad.append("byte_length 0")
    except sqlite3.IntegrityError:
        pass
    con.execute(sql.format(id="'ok1'", key="'same'", **base))
    try:
        con.execute(sql.format(id="'ok2'", key="'same'", **base))
        bad.append("duplicate storage key")
    except sqlite3.IntegrityError:
        pass
    con.rollback()
    con.close()
    check("CHECK and UNIQUE constraints refuse a bad kind, type, backend, empty size and a reused "
          "storage key", not bad)
    down = alembic(db, "downgrade", "022_engagement_roadmap_work_plan")
    check("downgrade to 022 removes exactly that table",
          down.returncode == 0 and set(inspector().get_table_names()) == before)
    body = read("alembic/versions/023_phase_task_evidence.py").split('"""', 2)[2].lower()
    check("migration 023 carries no data and alters no existing table",
          "insert" not in body and "op.execute" not in body and "add_column" not in body
          and "alter_column" not in body and body.count("create_table") == 1)


# --------------------------------------------------------------------------- 2-3. policy, storage


def policy_and_storage_checks(tmp):
    print("\n[2. persistence policy]")
    from peak.persistence import allowlist
    from peak.persistence import runtime_persistence as rp

    check("phase_task_evidence is append_only and not UPDATE-eligible",
          rp.RUNTIME_TABLE_PERSISTENCE.get(TABLE) == "append_only"
          and TABLE not in rp.update_eligible_tables() and rp.policy_problems() == [])
    actions = [a for (t, a) in allowlist.WORKSPACE_WRITE_COLUMNS if t == TABLE]
    check("the allowlist has one create action and nothing else",
          actions == ["create_phase_task_evidence"])

    print("\n[3. storage boundary]")
    from peak.workspace import evidence_storage as es

    store = es.FilesystemEvidenceStore(os.path.join(tmp, "s"))
    refused = 0
    for key in ("../x", "evidence/../../etc/passwd", "evidence/a/../b", "evidence/A/B", "/abs"):
        try:
            store.put(key, b"x", "image/png")
        except es.EvidenceStoreError:
            refused += 1
    check("the local store refuses keys outside its pattern", refused == 5)
    store.put("evidence/e1/v1", b"one", "image/png")
    try:
        store.put("evidence/e1/v1", b"two", "image/png")
        overwrote = True
    except es.EvidenceStoreError:
        overwrote = False
    check("the local store never overwrites a key", not overwrote
          and store.read("evidence/e1/v1") == b"one")
    check("the store has no delete or listing",
          not any(hasattr(store, n) for n in ("delete", "remove", "list", "list_keys")))
    env = {es.BACKEND_ENV: "filesystem", es.FILESYSTEM_ROOT_ENV: os.path.join(tmp, "s")}
    with mock.patch.dict(os.environ, env):
        local = es.store_from_environment("sqlite:///x.db")
        prod = es.store_from_environment("mysql+pymysql://u@h/db")
    with mock.patch.dict(os.environ, {es.BACKEND_ENV: ""}):
        unset = es.store_from_environment("sqlite:///x.db")
    check("filesystem storage is refused against a MySQL runtime; unset means capture off",
          local is not None and prod is None and unset is None)
    r2_checks(tmp)


#: Synthetic R2 settings: never real. The secret is a marker that must never be logged.
R2_FAKE = {"PEAK_R2_ACCOUNT_ID": "0123456789abcdef0123456789abcdef",
           "PEAK_R2_BUCKET": "peak-evidence-synthetic",
           "PEAK_R2_ACCESS_KEY_ID": "synthetic-access-key-id",
           "PEAK_R2_SECRET_ACCESS_KEY": "synthetic-secret-MUST-NOT-APPEAR"}


def r2_checks(tmp):
    print("\n[3b. R2 adapter (offline: stubbed, no network)]")
    import logging

    from botocore.stub import Stubber

    from peak.workspace import evidence_storage as es

    def configured(extra=None, url="mysql+pymysql://u@h/db"):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
        env.update({es.BACKEND_ENV: "r2", **R2_FAKE, **(extra or {})})
        with mock.patch.dict(os.environ, env, clear=True):
            return es.store_from_environment(url)

    store = configured()
    client = store._client if store is not None else None
    check("backend=r2 with all four variables builds the R2 store, also with a MySQL runtime",
          isinstance(store, es.R2EvidenceStore) and store.backend == "r2")
    check("the endpoint is derived from the account id, region 'auto', bucket from PEAK_R2_BUCKET",
          client is not None
          and client.meta.endpoint_url == f"https://{R2_FAKE['PEAK_R2_ACCOUNT_ID']}"
                                          ".r2.cloudflarestorage.com"
          and client.meta.region_name == "auto" and store.bucket == R2_FAKE["PEAK_R2_BUCKET"])
    check("the R2 store has only put, read and exists (no delete, list or bucket call)",
          not any(hasattr(store, n) for n in ("delete", "remove", "list", "list_keys", "copy"))
          and {n for n in vars(es.R2EvidenceStore) if not n.startswith("_")}
          == {"backend", "put", "read", "exists"})

    key, data = "evidence/eng_synthetic/ptevd_synthetic", b"\x89PNG\r\n\x1a\nsynthetic"
    bucket = R2_FAKE["PEAK_R2_BUCKET"]
    stub = Stubber(client)
    stub.add_response("put_object", {}, {"Bucket": bucket, "Key": key, "Body": data,
                                         "ContentType": "image/png", "IfNoneMatch": "*"})
    stub.add_client_error("put_object", "PreconditionFailed", http_status_code=412)
    stub.add_response("head_object", {}, {"Bucket": bucket, "Key": key})
    stub.add_client_error("head_object", "404", http_status_code=404)
    stub.add_client_error("head_object", "AccessDenied", http_status_code=403)
    stub.add_client_error("get_object", "NoSuchKey", http_status_code=404)
    stub.add_client_error("get_object", "InternalError", http_status_code=500)
    outcomes = []
    with stub:
        store.put(key, data, "image/png")
        for call in (lambda: store.put(key, data, "image/png"),):
            try:
                call()
                outcomes.append("overwrote")
            except es.EvidenceStoreError as exc:
                outcomes.append(str(exc))
        outcomes.append(store.exists(key))
        outcomes.append(store.exists(key))
        for call in (lambda: store.exists(key), lambda: store.read(key), lambda: store.read(key)):
            try:
                call()
                outcomes.append("no error")
            except es.EvidenceStoreError as exc:
                outcomes.append(str(exc))
        stub.assert_no_pending_responses()
    check("put is a conditional write (If-None-Match: *); an existing key is refused, never "
          "overwritten", outcomes[0] == "evidence key already exists")
    check("exists is true / false on 200 / 404 and fails closed (raises) on any other error",
          outcomes[1:4] == [True, False, "evidence storage request failed"])
    check("read reports a missing object and a failed request without detail",
          outcomes[4:] == ["evidence bytes not found", "evidence storage request failed"])
    refused = 0
    for bad in ("../x", "evidence/A/B", "other/a/b"):
        for call in (lambda: store.put(bad, b"x", "image/png"), lambda: store.read(bad),
                     lambda: store.exists(bad)):
            try:
                call()
            except es.EvidenceStoreError:
                refused += 1
    check("the R2 store refuses keys outside the server-generated pattern before any request",
          refused == 9)

    logger = logging.getLogger(es.__name__)
    seen = []
    handler = logging.Handler()
    handler.emit = lambda record: seen.append(record.getMessage())
    logger.addHandler(handler)
    try:
        incomplete = [configured({name: ""}) for name in es.R2_ENV]
        bad_account = configured({"PEAK_R2_ACCOUNT_ID": "evil.example/x"})
        no_fallback = configured({"PEAK_R2_BUCKET": "", es.FILESYSTEM_ROOT_ENV: tmp},
                                 url="sqlite:///x.db")
        unknown = configured({es.BACKEND_ENV: "s3"})
    finally:
        logger.removeHandler(handler)
    check("backend=r2 with any one variable missing turns capture off (no store)",
          incomplete == [None] * 4)
    check("an account id that is not 32 hex characters is refused (no endpoint injection)",
          bad_account is None)
    check("an incomplete R2 configuration never falls back to the local store", no_fallback is None)
    check("an unknown backend turns capture off", unknown is None)
    check("the reason is logged by variable name, never by value",
          seen and all("PEAK_" in m or "backend" in m for m in seen)
          and not any(v in m for m in seen for v in R2_FAKE.values() if v.startswith("synthetic")))


# --------------------------------------------------------------------------- 4-5. app


def _setup(tmp):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app
    from peak.db.session import create_session_factory
    from peak.workspace import evidence_storage as es

    db = os.path.join(tmp, "app.sqlite3")
    alembic(db, "upgrade", "head").check_returncode()
    factory = create_session_factory(url=f"sqlite:///{db}")
    people = {}
    for key, name, role in (("lee", "Lee Lead", "admin"), ("cam", "Cam Consultant", "consultant")):
        people[key] = accounts.create_consultant(factory, name=name, email=f"{key}@example.com",
                                                 role=role, password=PASSWORD)["id"]
    store = es.FilesystemEvidenceStore(os.path.join(tmp, "store"))
    app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True,
                     evidence_store=store, web_base_url=WEB_BASE)

    def client(who=None):
        c = TestClient(app, base_url="https://testserver")
        if who:
            r = c.post("/auth/login", json={"email": f"{who}@example.com", "password": PASSWORD})
            assert r.status_code == 200, r.text
        return c

    return app, factory, store, client, db


def _phase(lee, label, authorize=True):
    cid = lee.post("/clients", json={"organization_label": f"Synthetic {label}"}).json()["client"]["id"]
    eid = lee.post("/engagements", json={"client_id": cid, "engagement_label": label}
                   ).json()["engagement"]["id"]
    pid = lee.post(f"/engagements/{eid}/phases",
                   json={"title": "Receiving", "scope_summary": "Receiving accuracy",
                         "origin_note": "Synthetic phase for the Phase 220 check"}
                   ).json()["phase"]["id"]
    lee.post(f"/phases/{pid}/template-tasks", json={"template_key": "receiving_accuracy"})
    if authorize:
        r = lee.post(f"/phases/{pid}/authorization",
                     json={"authorization_basis": "Client agreed by email (synthetic)"})
        assert r.status_code == 200, r.text
    return pid, lee.get(f"/phases/{pid}").json()["phase"]


def _counts(db):
    con = sqlite3.connect(db)
    names = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}
    con.close()
    return out


def app_checks(tmp):
    print("\n[4. API]")
    from fastapi.testclient import TestClient

    from peak.consultant_api.app import create_app
    from peak.db.models import PhaseTaskEvidence
    from peak.workspace import phase_evidence as pe

    app, factory, store, client, db = _setup(tmp)
    lee, cam, anon = client("lee"), client("cam"), client()
    pid, phase = _phase(lee, "Alpha")
    tasks = phase["tasks"]
    task = next(t for t in tasks if t["requires_record"])
    other = next(t for t in tasks if t["id"] != task["id"])
    tid = task["id"]
    cam_id = cam.get("/auth/me").json()["consultant"]["id"]

    check("logged out, a task's evidence listing returns 401",
          anon.get(f"/tasks/{tid}/evidence").status_code == 401)
    listing = cam.get(f"/tasks/{tid}/evidence").json()["task_evidence"]
    up = listing["upload"]
    check("a signed-in consultant gets an empty listing and an upload grant",
          listing["evidence"] == [] and up["available"] is True and up["path"] == "/evidence-uploads"
          and up["max_bytes"] == pe.MAX_BYTES and set(up["media_types"]) == set(pe.MEDIA_TYPES))
    grant = up["grant"]
    before_list = _counts(db)
    cam.get(f"/tasks/{tid}/evidence")
    check("loading a task's evidence listing changes no table (a page load mutates nothing)",
          _counts(db) == before_list)

    def post(data, file=("IMG_0001.JPG", JPEG, "image/jpeg"), c=anon, **kw):
        return c.post("/evidence-uploads", data=data, files={"file": file}, **kw)

    check("no grant, or a forged grant, is refused (401 invalid_grant)",
          code(post({})) == "invalid_grant"
          and code(post({"grant": pe.upload_grant("another-secret-key-xxxxxxxxxxxxxxxx",
                                                  "x", tid)})) == "invalid_grant"
          and code(post({"grant": grant[:-2] + "xx"})) == "invalid_grant")
    with mock.patch("itsdangerous.timed.time.time", return_value=time.time() - 3600):
        old_grant = pe.upload_grant(SECRET, "unused", tid)
    with mock.patch("itsdangerous.timed.time.time", return_value=time.time() - 3600):
        stale = pe.upload_grant(SECRET, cam_id, tid)
    r_exp = post({"grant": stale})
    r_exp_web = post({"grant": stale, "respond": "redirect"}, follow_redirects=False)
    check("an expired grant is refused, and a browser is sent back to the task to retry",
          code(r_exp) == "upload_expired" and r_exp_web.status_code == 303
          and r_exp_web.headers["location"].endswith(
              f"/phases/{pid}/tasks/{tid}?evidence_error=upload_expired#evidence"))
    check("a grant for an unknown consultant is refused", code(post({"grant": old_grant})) ==
          "invalid_grant")

    before = _counts(db)
    readiness_before = lee.get(f"/phases/{pid}").json()["phase"]["readiness"]
    r = post({"grant": grant, "evidence_kind": "document_photo",
              "caption": "Packing slip for PO 1042 on dock 3"},
             file=("../../etc/IMG_0001.JPG", JPEG, "image/png"))
    item = r.json().get("evidence", {})
    check("a JPEG upload is stored (201), its type decided from the bytes, not the declared type",
          r.status_code == 201 and item["media_type"] == "image/jpeg"
          and item["evidence_kind"] == "document_photo" and item["interpreted"] is False)
    check("the sha256 and byte length are recorded",
          item["content_hash"] == hashlib.sha256(JPEG).hexdigest() and item["byte_length"] == len(JPEG))
    with factory() as s:
        row = s.get(PhaseTaskEvidence, item["id"])
        key, fname, backend = row.storage_key, row.file_name, row.storage_backend
        linkage = (row.task_id, row.phase_id, row.engagement_id, row.client_id)
    check("the storage key is server-generated under the engagement, the device name kept as a "
          "plain base name",
          re.fullmatch(rf"evidence/{linkage[2]}/{item['id']}", key) is not None
          and fname == "IMG_0001.JPG" and backend == "filesystem" and store.read(key) == JPEG)
    check("the row is linked to its task, phase, engagement and client",
          linkage[0] == tid and linkage[1] == pid and all(linkage))

    after = _counts(db)
    changed = {t for t in after if after[t] != before.get(t)}
    check("an upload adds one evidence row and changes no other table (no observation, finding, "
          "recommendation, assessment evidence, task record or artifact)",
          changed == {TABLE} and after[TABLE] == before[TABLE] + 1)
    phase_after = lee.get(f"/phases/{pid}").json()["phase"]
    t_after = next(t for t in phase_after["tasks"] if t["id"] == tid)
    check("task status and phase readiness are unchanged",
          t_after["status"] == task["status"] and phase_after["readiness"] == readiness_before)
    check("evidence does not satisfy the task's record requirement",
          t_after["work_state"]["record_missing"] is True
          and code(lee.post(f"/tasks/{tid}/completion", json={"result_summary": "Done"}))
          not in (200, 201))

    check("a renamed GIF, an empty file and an oversize file are refused",
          code(post({"grant": grant}, file=("x.jpg", b"GIF89a" + bytes(32), "image/jpeg")))
          == "unsupported_type"
          and code(post({"grant": grant}, file=("x.jpg", b"", "image/jpeg"))) == "empty_file"
          and code(post({"grant": grant},
                        file=("big.jpg", JPEG[:4] + bytes(pe.MAX_BYTES), "image/jpeg")))
          == "file_too_large")
    r_png = post({"grant": grant}, file=("a.png", PNG, "image/png"))
    r_heic = post({"grant": grant}, file=("a.HEIC", HEIC, "application/octet-stream"))
    check("PNG and HEIC are accepted as their own types",
          r_png.status_code == 201 and r_png.json()["evidence"]["media_type"] == "image/png"
          and r_heic.status_code == 201
          and r_heic.json()["evidence"]["media_type"] == "image/heic")
    check("an unknown field or kind is refused",
          code(post({"grant": grant, "evidence_kind": "finding"})) == "invalid_field"
          and code(post({"grant": grant, "caption": "x" * 501})) == "invalid_field")

    # Linking to a record: only a current record of the same task.
    rec = lee.post(f"/tasks/{tid}/records",
                   json={"record_kind": "note", "record_text": "Slip matched PO"}).json()
    rec_task = next(t for t in rec["phase"]["tasks"] if t["id"] == tid)
    rec_id = rec_task["records"][-1]["id"]
    rec2 = lee.post(f"/tasks/{other['id']}/records",
                    json={"record_kind": "note", "record_text": "Other task note"}).json()
    other_rec = next(t for t in rec2["phase"]["tasks"] if t["id"] == other["id"])["records"]
    r_link = post({"grant": grant, "task_record_id": rec_id})
    check("evidence can be linked to a current record of the same task",
          r_link.status_code == 201 and r_link.json()["evidence"]["task_record"]["id"] == rec_id)
    lee.post(f"/tasks/{tid}/records", json={"record_kind": "note", "record_text": "Corrected",
                                            "supersedes_record_id": rec_id})
    check("linking to another task's record, an unknown record or a corrected record is refused",
          code(post({"grant": grant, "task_record_id": other_rec[-1]["id"]})) == "invalid_link"
          and code(post({"grant": grant, "task_record_id": "ptrec_nope"})) == "invalid_link"
          and code(post({"grant": grant, "task_record_id": rec_id})) == "invalid_link")

    # Cross-engagement: a grant for one task cannot reach another engagement's evidence.
    pid_b, phase_b = _phase(lee, "Beta")
    tid_b = phase_b["tasks"][0]["id"]
    grant_b = cam.get(f"/tasks/{tid_b}/evidence").json()["task_evidence"]["upload"]["grant"]
    check("another engagement's task cannot replace or link to this task's evidence",
          code(post({"grant": grant_b, "supersedes_evidence_id": item["id"]})) == "invalid_link"
          and code(post({"grant": grant_b, "task_record_id": rec_id})) == "invalid_link")

    # Supersession.
    r_rep = post({"grant": grant, "supersedes_evidence_id": item["id"], "caption": "Clearer photo"})
    check("a replacement supersedes the earlier capture; both are kept",
          r_rep.status_code == 201
          and r_rep.json()["evidence"]["supersedes_evidence_id"] == item["id"])
    check("evidence is replaced at most once (already_replaced)",
          code(post({"grant": grant, "supersedes_evidence_id": item["id"]})) == "already_replaced")
    listing = cam.get(f"/tasks/{tid}/evidence").json()["task_evidence"]
    first = next(e for e in listing["evidence"] if e["id"] == item["id"])
    check("the listing marks the replaced capture and keeps it",
          first["superseded_by"] == r_rep.json()["evidence"]["id"])
    text = str(listing)
    check("listings never include the storage key, the device file name or a store path",
          "storage_key" not in text and key not in text and "IMG_0001" not in text
          and "file_name" not in text and store.root not in text)

    # Content.
    path = first["content_path"]
    got = anon.get(path)
    h = got.headers
    check("content is served unchanged through a signed token, without a session",
          got.status_code == 200 and got.content == JPEG and h["content-type"] == "image/jpeg")
    check("content headers: nosniff, sandboxed CSP, private cache, no referrer, inline with a "
          "server name",
          h["x-content-type-options"] == "nosniff" and "sandbox" in h["content-security-policy"]
          and h["cache-control"].startswith("private") and h["referrer-policy"] == "no-referrer"
          and h["content-disposition"] == f'inline; filename="evidence-{item["id"]}.jpg"')
    with mock.patch("itsdangerous.timed.time.time", return_value=time.time() - 3600):
        expired_path = "/evidence-content/" + pe.content_token(SECRET, item["id"])
    check("a tampered, expired or unknown content token returns 404",
          anon.get(path[:-2] + "xx").status_code == 404
          and anon.get(expired_path).status_code == 404
          and anon.get("/evidence-content/" + pe.content_token(SECRET, "ptevd_nope")).status_code
          == 404)
    with open(os.path.join(store.root, *key.split("/")), "r+b") as f:
        f.seek(20)
        f.write(b"\x00\x01")
    check("bytes that no longer match their recorded hash are refused (content_mismatch)",
          code(anon.get(path)) == "content_mismatch")

    # Browser upload: redirect back to the task.
    r_web = post({"grant": grant, "respond": "redirect"}, follow_redirects=False)
    check("a browser upload is sent back to the task page (303, evidence=added)",
          r_web.status_code == 303 and r_web.headers["location"]
          == f"{WEB_BASE}/phases/{pid}/tasks/{tid}?evidence=added#evidence")
    r_web_bad = post({"grant": grant, "respond": "redirect"}, file=("x.gif", b"GIF89a", "image/gif"),
                     follow_redirects=False)
    check("a refused browser upload is sent back with its code",
          r_web_bad.status_code == 303
          and r_web_bad.headers["location"].endswith("?evidence_error=unsupported_type#evidence"))

    # Capture closes with the task and is not open before authorization.
    planned_pid, planned = _phase(lee, "Gamma", authorize=False)
    planned_tid = planned["tasks"][0]["id"]
    pl = cam.get(f"/tasks/{planned_tid}/evidence").json()["task_evidence"]
    check("a planned phase offers no upload and says why", pl["upload"]["available"] is False
          and pl["upload"]["reason"])
    planned_grant = pe.upload_grant(SECRET, cam_id,
                                    planned_tid)
    check("an upload to a planned phase's task is refused (phase_not_authorized)",
          code(post({"grant": planned_grant})) == "phase_not_authorized")
    na = lee.post(f"/tasks/{other['id']}/not-applicable",
                  json={"reason": "No inbound deliveries in scope"})
    grant_other = cam.get(f"/tasks/{other['id']}/evidence").json()["task_evidence"]["upload"]
    check("a resolved task offers no upload, and an earlier grant is refused (task_resolved)",
          na.status_code == 200 and grant_other["available"] is False
          and code(post({"grant": pe.upload_grant(SECRET, "x", other["id"])})) in ("invalid_grant",)
          and code(post({"grant": pe.upload_grant(
              SECRET, cam_id, other["id"])}))
          == "task_resolved")

    # No edit or removal path.
    evidence_routes = [(sorted(r.methods or []), r.path) for r in app.routes
                       if "evidence" in getattr(r, "path", "")]
    check("evidence routes are only list, upload and content (no edit or delete)",
          # Phase 221 adds one read: an engagement's captures and observation links.
          sorted(p for _, p in evidence_routes)
          == ["/engagements/{engagement_id}/evidence", "/evidence-content/{token}",
              "/evidence-uploads", "/tasks/{task_id}/evidence"]
          and not any(m in ("DELETE", "PUT", "PATCH") for ms, _ in evidence_routes for m in ms))
    refused = []
    for change in (lambda s, e: setattr(e, "caption", "edited"), lambda s, e: s.delete(e)):
        with factory() as s:
            e = s.get(PhaseTaskEvidence, item["id"])
            try:
                change(s, e)
                s.commit()
            except Exception:  # noqa: BLE001 - the insert-only listener raises
                refused.append(True)
    check("the ORM refuses to update or delete an evidence row", refused == [True, True])

    from peak.workspace import evidence_storage as es

    half = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    half.update({es.BACKEND_ENV: "r2", "PEAK_R2_BUCKET": "peak-evidence-synthetic"})
    with mock.patch.dict(os.environ, half, clear=True):
        off_app = create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True,
                             web_base_url=WEB_BASE)
    off = TestClient(off_app, base_url="https://testserver")
    off.post("/auth/login", json={"email": "cam@example.com", "password": PASSWORD})
    off_list = off.get(f"/tasks/{tid}/evidence").json()["task_evidence"]
    check("with backend=r2 but its configuration incomplete, the API still starts, capture is "
          "off and an upload is refused (503); nothing falls back",
          off_list["upload"]["available"] is False
          and off.post("/evidence-uploads", data={"grant": grant},
                       files={"file": ("a.jpg", JPEG, "image/jpeg")}).status_code == 503)
    check("with capture off, unrelated routes still work (health, the phase, the task)",
          off.get("/healthz").status_code == 200
          and off.get(f"/phases/{pid}").status_code == 200)
    check("with capture off, existing evidence cannot be read from another store (503)",
          off.get(path).status_code == 503)


# --------------------------------------------------------------------------- 6. static


def _visible_text(sources):
    out = []
    for s in sources:
        s = re.sub(r"/\*.*?\*/|^\s*//.*$", "", s, flags=re.DOTALL | re.MULTILINE)
        out += re.findall(r'"([^"\n]{3,})"', s) + re.findall(r">([^<>{}\n]{3,})<", s)
    return out


_EVIDENCE_FETCH_RUNNER = """
const fs = require("fs");
const ts = require(process.argv[2]);
const src = fs.readFileSync(process.argv[3], "utf8");
const js = ts.transpileModule(src, { compilerOptions: { module: ts.ModuleKind.CommonJS,
                                                        target: ts.ScriptTarget.ES2020 } }).outputText;
class Nav extends Error {}
const stubs = {
  "server-only": {}, "react": { cache: (f) => f },
  "next/headers": { cookies: async () => ({ get: () => ({ value: "tok" }) }) },
  "next/navigation": { notFound: () => { throw new Nav("notFound"); },
                       redirect: (to) => { throw new Nav("redirect:" + to); } },
};
const mod = { exports: {} };
new Function("module", "exports", "require", js)(mod, mod.exports, (n) => stubs[n]);
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
(async () => {
  const out = [];
  for (const c of cases) {
    const calls = [];
    global.fetch = async (url, init) => {
      calls.push({ url, method: (init && init.method) || "GET" });
      if (c.throws) throw new Error("connection refused");
      return new Response(c.body === undefined ? "" : JSON.stringify(c.body), { status: c.status });
    };
    let result, error = null;
    try { result = await mod.exports.getTaskEvidence("ptask_x"); }
    catch (e) { error = e instanceof Nav ? e.message : "throw:" + e.message; }
    out.push({ result: result === undefined ? null : result, error, calls });
  }
  process.stdout.write(JSON.stringify(out));
})();
"""


def evidence_fetch_checks(tmp):
    print("\n[5b. task page: evidence is optional (getTaskEvidence under Node)]")
    node = shutil.which("node")
    if node is None or not os.path.isdir(os.path.join(WEB, "node_modules", "typescript")):
        print("  [skip] Node or web/node_modules not installed")
        return
    script = os.path.join(tmp, "evidence_fetch.cjs")
    with open(script, "w", encoding="utf-8") as f:
        f.write(_EVIDENCE_FETCH_RUNNER)
    live = {"task_id": "ptask_x", "phase_id": "p", "evidence": [{"id": "ptevd_1"}],
            "upload": {"available": True, "path": "/evidence-uploads", "grant": "g",
                       "max_bytes": 1, "media_types": []}}
    off = {**live, "evidence": [], "upload": {"available": False, "reason": "Not available."}}
    cases = [{"status": 200, "body": {"task_evidence": live}},
             {"status": 200, "body": {"task_evidence": off}},
             {"status": 404, "body": {"detail": "Not Found"}},
             {"status": 503, "body": {"detail": "x"}},
             {"status": 500},
             {"throws": True},
             {"status": 200, "body": {"something": "else"}},
             {"status": 401, "body": {"detail": "x"}}]
    out = subprocess.run([node, script, os.path.join(WEB, "node_modules", "typescript"),
                          os.path.join(WEB, "lib", "api.ts")],
                         input=json.dumps(cases), capture_output=True, text=True)
    if out.returncode != 0:
        check("getTaskEvidence runs under Node", False)
        print("    " + out.stderr.strip()[-400:])
        return
    r = json.loads(out.stdout)
    check("evidence available: the API's evidence is returned unchanged",
          r[0]["result"] == live and r[0]["error"] is None)
    check("storage disabled: the clean unavailable state (with its reason) is returned unchanged",
          r[1]["result"] == off and r[1]["error"] is None)
    check("endpoint absent (404), unavailable (503), failing (500), unreachable or answering "
          "something else: null, never notFound() or an error",
          all(x["result"] is None and x["error"] is None for x in r[2:7]))
    check("a missing session still goes to /login", r[7]["error"] == "redirect:/login")
    check("loading evidence is a single GET of the task's evidence (no mutation)",
          all(x["calls"] == [{"url": "http://127.0.0.1:8000/tasks/ptask_x/evidence",
                              "method": "GET"}] for x in r))
    page = read(UI_FILES[3])
    check("the task page loads evidence only through getTaskEvidence, says when it is "
          "unavailable, and loads the phase as before",
          "getTaskEvidence(t.id)" in page and "/evidence`" not in page
          and "Photos and documents are currently unavailable." in page
          and "apiGet<{ phase: EngagementPhaseDetail }>" in page)
    check("apiGet itself is unchanged (404 is still notFound() everywhere else)",
          re.search(r"export async function apiGet[^}]*if \(res\.status === 404\) notFound\(\);",
                    read("web/lib/api.ts"), re.S) is not None)


def static_checks():
    print("\n[6. static UI checks]")
    check("the new UI files exist", all(os.path.exists(os.path.join(REPO_ROOT, p)) for p in UI_FILES))
    ui = {p: read(p) for p in UI_FILES}
    form = ui["web/components/evidence-capture.tsx"]
    check("the form posts multipart straight to the API with the grant and asks to be sent back",
          'method="post"' in form and 'encType="multipart/form-data"' in form
          and 'name="grant"' in form and 'name="respond" value="redirect"' in form
          and 'type="file"' in form)
    from peak.workspace import phase_evidence as pe

    accept = re.search(r'EVIDENCE_ACCEPT = "([^"]+)"', ui["web/lib/evidence.ts"]).group(1)
    check("the accepted types match the API", set(accept.split(",")) == set(pe.MEDIA_TYPES))
    check("the camera is offered by the device, not forced (no capture attribute)",
          "capture=" not in form)
    check("an upload shows that it is in progress", "Uploading…" in form)
    page = ui["web/app/(workspace)/phases/[id]/tasks/[taskId]/page.tsx"]
    check("the task page reads its evidence and has an evidence section",
          "getTaskEvidence(" in page and 'id="evidence"' in page and "apiPublicUrl()" in page)
    check("the API's refusal codes all have a consultant-facing message",
          all(f"{c}:" in ui["web/lib/evidence.ts"] for c in (
              "empty_file", "file_too_large", "unsupported_type", "invalid_link",
              "already_replaced", "upload_expired", "storage_unavailable", "task_resolved")))
    web_sources = []
    for root, dirs, files in os.walk(WEB):
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next")]
        web_sources += [read(os.path.relpath(os.path.join(root, f), REPO_ROOT))
                        for f in files if f.endswith((".ts", ".tsx"))]
    check("the web app never handles a storage key, bucket or store path",
          not any(re.search(r"storage_key|bucket|PEAK_EVIDENCE_", s) for s in web_sources))
    check("no evidence code calls an observation, finding or report endpoint",
          not any(re.search(r"/observations|/findings|/final-report|/assessment", s)
                  for s in ui.values()))
    from peak.workspace import advisory_boundary as b

    hits = {t for t in _visible_text(ui.values()) if b.framing_violations(t)}
    check("no audit / compliance / deficiency language in the new UI text", not hits)
    if hits:
        print("    " + "; ".join(sorted(hits)))
    service = read("peak/workspace/phase_evidence.py")
    check("the service never reads image content (no OCR, EXIF or image library)",
          not re.search(r"^\s*(import|from)\s+(PIL|exif|pytesseract|cv2|piexif)", service, re.M))
    p218 = ("web/components/work-plan-record-form.tsx", "web/components/work-plan-actions.tsx",
            "web/components/work-plan-parts.tsx", "web/app/(workspace)/phases/[id]/page.tsx")
    check("Phase 218 work-plan files still carry no file input",
          not any('type="file"' in read(p) for p in p218 + (UI_FILES[3],)))
    reqs = read("requirements-web.txt")
    check("requirements-web.txt declares the multipart parser and boto3",
          "python-multipart" in reqs and re.search(r"^boto3>=", reqs, re.M) is not None)
    check("docs/PHASE220_GUIDED_EVIDENCE_CAPTURE.md exists",
          os.path.exists(os.path.join(REPO_ROOT, "docs/PHASE220_GUIDED_EVIDENCE_CAPTURE.md")))


def main() -> int:
    print("Peak Phase 220 guided evidence capture check")
    print("=" * 45)
    try:
        import argon2, boto3, fastapi, httpx, itsdangerous, multipart, sqlalchemy  # noqa: F401,E401
    except ImportError:
        print("  [skip] web dependencies not installed — run with PYTHON=.venv/bin/python")
        return 0
    with tempfile.TemporaryDirectory(prefix="peak_phase220_") as tmp:
        migration_checks(tmp)
        policy_and_storage_checks(tmp)
        app_checks(tmp)
        evidence_fetch_checks(tmp)
    static_checks()

    print("\nSummary")
    print(f"  failures : {len(_failures)}")
    print("RESULT: " + ("PASS" if not _failures else "FAIL"))
    return 0 if not _failures else 1


if __name__ == "__main__":
    sys.exit(main())

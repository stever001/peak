#!/usr/bin/env python3
"""Phase 212 artifact version persistence check (offline; temporary SQLite only).

Proves:

1. an artifact can be created for an engagement;
2. the first version stores the canonical FinalReport content;
3. the hash is deterministic for identical content;
4. changed content creates a different version and hash;
5. the earlier version remains unchanged;
6. the supersedes relationship is preserved;
7. version content cannot be updated through the service (or the ORM);
8. no client-facing version metadata is introduced.

Plus migration 018 structure. The report is composed from a real workspace engagement through the
Phase 206 assessment and the Phase 208 composer. No network, no credential, no production contact.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
CONSULTANT = "cons_phase212"
NORTH_STAR = "Count what we hold, every week"
NORTH_STAR_2 = "Count what we hold, every day"
OBSERVATION = "Bin labels are handwritten in the overflow aisle."
PHASE_LABEL = "Assessment"


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def raises(fn, exc=Exception):
    try:
        fn()
    except exc:
        return True
    return False


def alembic(env, *args):
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True)


def migration_checks(tmp):
    print("\n[migration 018]")
    db = os.path.join(tmp, "mig.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    import sqlalchemy as sa

    up = alembic(env, "upgrade", "018_artifact_versions")
    tables = set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())
    check("upgrade to 018 adds artifacts and artifact_versions",
          up.returncode == 0 and {"artifacts", "artifact_versions"} <= tables)
    down = alembic(env, "downgrade", "017_discovery_workflow")
    tables = set(sa.inspect(sa.create_engine(f"sqlite:///{db}")).get_table_names())
    check("downgrade to 017 removes exactly those two tables",
          down.returncode == 0 and not {"artifacts", "artifact_versions"} & tables
          and "discovery_observations" in tables)
    src = open(os.path.join(REPO_ROOT, "alembic/versions/018_artifact_versions.py")).read()
    code = src.split('"""', 2)[2].lower()  # the module body, after the docstring
    check("migration 018 carries no data (no INSERT, no bulk insert, no raw SQL)",
          "insert" not in code and "op.execute" not in code)


def build(tmp):
    db = os.path.join(tmp, "app.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    alembic(env, "upgrade", "head").check_returncode()
    from peak.db.session import create_session_factory

    factory = create_session_factory(url=f"sqlite:///{db}")
    import init_discovery_questions as init

    init.initialize(factory)
    return factory


def compose(factory, engagement_id):
    """The Phase 208 FinalReport, composed exactly as the report route composes it."""
    from peak.reports.final_report import compose_final_report
    from peak.workflows.consultant_assessment_workflow import build_consultant_internal_assessment
    from peak.workspace import get_engagement

    engagement = get_engagement(factory, engagement_id)
    with factory() as session:
        result = build_consultant_internal_assessment(session.connection(), engagement_id)
    return compose_final_report(result.assessment, engagement)


def persistence_checks(factory):
    from sqlalchemy import select, update

    from peak.db.models import Artifact, ArtifactVersion, Engagement
    from peak.persistence import allowlist
    from peak.workspace import WorkspaceError, create_client, create_engagement
    from peak.workspace import artifacts as av
    from peak.workspace.discovery import create_observation, set_north_star

    client = create_client(factory, {"organization_label": "Synthetic Co 212"})
    engagement = create_engagement(factory, {"client_id": client["id"],
                                             "engagement_label": "Synthetic engagement 212",
                                             "current_phase": PHASE_LABEL})
    eid = engagement["id"]
    set_north_star(factory, eid, {"north_star": NORTH_STAR})
    obs = create_observation(factory, eid, {"observation_text": OBSERVATION}, CONSULTANT)

    print("\n[1. artifact created for an engagement]")
    artifact = av.create_artifact(factory, eid, av.ARTIFACT_TYPE_FINAL_REPORT, CONSULTANT)
    check("artifact carries client, engagement, type and the phase-label snapshot",
          artifact["engagement_id"] == eid and artifact["client_id"] == client["id"]
          and artifact["artifact_type"] == "final_report"
          and artifact["engagement_phase_label"] == PHASE_LABEL and artifact["versions"] == [])
    with factory() as s:
        row = s.get(Artifact, artifact["id"])
        stamped = (row.owner_id, row.authorization_scope) == ("peak_consultants",
                                                               "engagement_authorized")
    check("artifact is stamped peak_consultants / engagement_authorized", stamped)
    check("an unknown artifact type is refused",
          raises(lambda: av.create_artifact(factory, eid, "proposal", CONSULTANT), WorkspaceError))
    check("an unknown engagement yields None",
          av.create_artifact(factory, "eng_missing", "final_report", CONSULTANT) is None)
    with factory() as s:
        s.add(Engagement(id="eng_anchor212", client_id=client["id"], owner_id="someone_else",
                         authorization_scope="internal_test"))
        s.commit()
    check("an engagement without the workspace stamp is refused",
          raises(lambda: av.create_artifact(factory, "eng_anchor212", "final_report", CONSULTANT),
                 WorkspaceError))

    print("\n[2. first version stores canonical FinalReport content]")
    report1 = compose(factory, eid)
    v1 = av.create_final_report_version(factory, artifact["id"], report1, CONSULTANT)
    expected = av.final_report_content(report1)
    check("version 1 is created, numbered 1, status versioned, superseding nothing",
          v1["created"] and v1["version_number"] == 1 and v1["version_status"] == "versioned"
          and v1["supersedes_version_id"] is None)
    check("stored content equals the report's canonical business content",
          v1["content"] == expected and v1["content"]["executive_overview"]["north_star"] == NORTH_STAR)
    check("the six report sections are in the stored content",
          all(k in v1["content"] for k in report1.section_order))
    check("draft-state flags are not part of the content",
          not {"approved_for_client", "client_facing", "status", "audience",
               "requires_human_review"} & set(v1["content"]))
    check("content format is named and the stored hash re-verifies",
          v1["content_format"] == av.FINAL_REPORT_CONTENT_FORMAT and v1["hash_verified"])
    refs = v1["source_references"]
    check("provenance: creator, composer and the referenced observation are recorded",
          v1["created_by_consultant_id"] == CONSULTANT and v1["created_at"]
          and refs["composer"] == av.COMPOSER and obs["id"] in refs["discovery_observation_ids"])

    print("\n[3. deterministic hash]")
    report1b = compose(factory, eid)
    h1 = av.content_hash(av.canonical_json(av.final_report_content(report1)))
    h1b = av.content_hash(av.canonical_json(av.final_report_content(report1b)))
    check("two independent compositions of unchanged state hash identically",
          h1 == h1b == v1["content_hash"] and len(h1) == 64)
    check("key order does not affect the canonical form",
          av.canonical_json({"b": 1, "a": [{"d": 2, "c": 3}]})
          == av.canonical_json({"a": [{"c": 3, "d": 2}], "b": 1}))
    from peak.reports.final_report import render_final_report_markdown
    from peak.reports.final_report_docx import render_final_report_docx

    render_final_report_markdown(report1b)
    render_final_report_docx(report1b)
    check("rendering Markdown or DOCX does not change the hash",
          av.content_hash(av.canonical_json(av.final_report_content(report1b))) == h1)
    again = av.create_final_report_version(factory, artifact["id"], report1b, CONSULTANT)
    with factory() as s:
        count = len(s.scalars(select(ArtifactVersion)).all())
    check("identical content creates no new version (the latest is returned)",
          not again["created"] and again["id"] == v1["id"] and count == 1)

    print("\n[4. changed content creates a new version and hash]")
    set_north_star(factory, eid, {"north_star": NORTH_STAR_2})
    v2 = av.create_final_report_version(factory, artifact["id"], compose(factory, eid), CONSULTANT)
    check("version 2 is created with a different id and hash",
          v2["created"] and v2["version_number"] == 2 and v2["id"] != v1["id"]
          and v2["content_hash"] != v1["content_hash"]
          and v2["content"]["executive_overview"]["north_star"] == NORTH_STAR_2)

    print("\n[5. the earlier version is unchanged]")
    v1_now = av.get_artifact_version(factory, v1["id"])
    check("version 1 keeps its content, hash and status",
          v1_now["content"] == v1["content"] and v1_now["content_hash"] == v1["content_hash"]
          and v1_now["hash_verified"] and v1_now["version_status"] == "versioned"
          and v1_now["content"]["executive_overview"]["north_star"] == NORTH_STAR)

    print("\n[6. supersession preserved]")
    listing = av.get_artifact(factory, artifact["id"])
    check("version 2 supersedes version 1, and version 1 reports its successor",
          v2["supersedes_version_id"] == v1["id"] and v1_now["superseded_by_version_id"] == v2["id"])
    check("the artifact lists both versions in order, without content",
          [v["id"] for v in listing["versions"]] == [v1["id"], v2["id"]]
          and all("content" not in v for v in listing["versions"]))

    def second_successor():
        with factory() as s:
            s.add(ArtifactVersion(id="artv_branch", artifact_id=artifact["id"],
                                  client_id=client["id"], engagement_id=eid, version_number=3,
                                  content_format="x", content_canonical="{}", content_hash="0" * 64,
                                  supersedes_version_id=v1["id"],
                                  created_by_consultant_id=CONSULTANT))
            s.commit()

    check("the database refuses a second version superseding version 1 (history stays linear)",
          raises(second_successor))

    print("\n[7. version content cannot be updated]")
    public = {n for n in dir(av) if not n.startswith("_") and callable(getattr(av, n))}
    check("the service has no update, edit, set or delete function",
          not {n for n in public if any(w in n for w in ("update", "edit", "set_", "delete",
                                                         "remove", "replace"))})
    artifact_pairs = {k for k in allowlist.WORKSPACE_WRITE_COLUMNS
                      if k[0] in allowlist.ARTIFACT_RECORD_TABLES}
    check("the allowlist holds only the two create actions for artifact tables",
          artifact_pairs == {("artifacts", "create_artifact"),
                             ("artifact_versions", "create_artifact_version")})
    check("an update action on artifact_versions is refused by the write predicate",
          not allowlist.is_allowed_workspace_write("artifact_versions", "update_artifact_version",
                                                   ["content_canonical"]))

    def orm_edit():
        with factory() as s:
            s.get(ArtifactVersion, v1["id"]).content_canonical = "{}"
            s.commit()

    def bulk_edit():
        with factory() as s:
            s.execute(update(ArtifactVersion).where(ArtifactVersion.id == v1["id"])
                      .values(content_hash="f" * 64))
            s.commit()

    def orm_delete():
        with factory() as s:
            s.delete(s.get(ArtifactVersion, v1["id"]))
            s.commit()

    check("an ORM edit of version content is refused", raises(orm_edit, PermissionError))
    check("a bulk UPDATE of a version is refused", raises(bulk_edit, PermissionError))
    check("deleting a version is refused", raises(orm_delete, PermissionError))
    final = av.get_artifact_version(factory, v1["id"])
    check("after those attempts version 1 is byte-for-byte unchanged",
          final["content"] == v1["content"] and final["content_hash"] == v1["content_hash"]
          and final["hash_verified"])
    return report1, v1


def client_facing_checks(report, v1):
    print("\n[8. no client-facing version metadata]")
    fields = {f.name for f in dataclasses.fields(report)}
    check("FinalReport gains no version or artifact field",
          not {n for n in fields if "version" in n or "artifact" in n})
    from peak.reports.final_report import render_final_report_markdown
    from peak.reports.final_report_docx import render_final_report_docx

    markdown = render_final_report_markdown(report)
    docx = render_final_report_docx(report)
    check("the rendered report carries no version id, artifact id or hash",
          all(token not in markdown and token.encode() not in docx
              for token in (v1["id"], v1["artifact_id"], v1["content_hash"])))
    app_src = open(os.path.join(REPO_ROOT, "peak/consultant_api/app.py")).read()
    # Claims about this phase only (Phase 121 convention): Phase 213 legitimately adds internal
    # artifact review routes and UI. The durable invariant is that reading the report never
    # creates a version, checked below for the report and DOCX routes.
    import _schema_history as schema_history

    if schema_history.phase_never_committed(
            REPO_ROOT, "tests/validate_phase212_artifact_version_persistence.py"):
        check("the API neither exposes nor calls artifact versioning (no auto-versioning on read)",
              "artifact" not in app_src.lower())
        hits = subprocess.run(["git", "-C", REPO_ROOT, "grep", "-il", "artifact", "--", "web/app",
                               "web/components", "web/lib"], capture_output=True, text=True).stdout
        check("the web app shows no artifact or version metadata", not hits.strip())
    start = app_src.find("def _final_report(")
    end = app_src.find("return Response(", start)
    read_routes = app_src[start:end]
    check("the report and DOCX read routes never create a version (no auto-versioning on read)",
          start != -1 and end != -1 and "version" not in read_routes.lower())


def main() -> int:
    print("Phase 212 — Artifact version persistence foundation")
    tmp = tempfile.mkdtemp()
    try:
        migration_checks(tmp)
        report, v1 = persistence_checks(build(tmp))
        client_facing_checks(report, v1)
    finally:
        import shutil

        shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "=" * 56)
    print("Summary")
    print(f"  failures : {len(_failures)}")
    for failure in _failures:
        print(f"    - {failure}")
    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'}")
    return 1 if _failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

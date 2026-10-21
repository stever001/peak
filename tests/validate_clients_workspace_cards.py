#!/usr/bin/env python3
"""Clients workspace cards — consultant-facing presentation (offline; temporary SQLite only).

Proves:
1. the normal Clients list (``GET /clients`` without a filter) and the engagement form's Internal
   Test chooser (``?internal_test=true``) hide a retired internal-test client (one whose
   engagements have all been retired), while its record stays readable and real clients are
   unaffected;
2. an internal-test client with an active engagement, or with none yet, stays listed;
3. ``engagement_count`` counts active engagements only;
4. the card's secondary line (``web/lib/client-card.ts``, run under Node) leaves a missing location
   or contact out instead of describing it, says "N active engagement(s)" with the right number,
   and shows no count at zero;
5. the Clients page renders the Internal Test badge compactly beside the name, carries no
   placeholder copy, and its search placeholder names only the fields the API searches.

Exit status: 0 all checks passed; 1 a check failed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_failures = []
PASSWORD = "synthetic-password-cards"
SECRET = "synthetic-secret-cards-" + "x" * 32
CARD_HELPER = os.path.join(REPO_ROOT, "web", "lib", "client-card.ts")
CLIENTS_PAGE = os.path.join(REPO_ROOT, "web", "app", "(workspace)", "clients", "page.tsx")


def check(label, ok):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        _failures.append(label)


def build(tmp):
    db = os.path.join(tmp, "app.sqlite3")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PEAK_")}
    env["PEAK_DATABASE_URL"] = f"sqlite:///{db}"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=REPO_ROOT, env=env,
                   capture_output=True, text=True).check_returncode()
    from peak.db.session import create_session_factory

    return create_session_factory(url=f"sqlite:///{db}")


def api_checks(factory):
    from fastapi.testclient import TestClient

    from peak import accounts
    from peak.consultant_api.app import create_app

    accounts.create_consultant(factory, name="Ada Admin", email="ada@example.com", role="admin",
                               password=PASSWORD)
    ada = TestClient(create_app(session_factory=factory, secret_key=SECRET, secure_cookie=True),
                     base_url="https://testserver")
    ada.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})

    def client(label, **extra):
        return ada.post("/clients", json={"organization_label": label, **extra}).json()["client"]["id"]

    def engagement(cid, label, internal=False):
        body = {"client_id": cid, "engagement_label": label}
        if internal:
            body.update(internal_test=True, internal_test_confirmed=True)
        return ada.post("/engagements", json=body).json()["engagement"]["id"]

    def retire(eid, label):
        return ada.post(f"/engagements/{eid}/internal-test-deletion",
                        json={"confirm_engagement_label": label}).status_code

    real = client("Acme Distribution", city="Denver", country="USA", contact_name="Pat Lee")
    bare = client("Bare Co")
    engagement(real, "Acme Assessment")
    engagement(real, "Acme Follow-up")
    retired_only = client("Retired Test Co", internal_test=True)
    check("a retired internal-test client is set up (its only engagement retired)",
          retire(engagement(retired_only, "Retired Run", internal=True), "Retired Run") == 200)
    mixed = client("Mixed Test Co", internal_test=True)
    engagement(mixed, "Mixed Active", internal=True)
    retire(engagement(mixed, "Mixed Old", internal=True), "Mixed Old")
    fresh = client("Fresh Test Co", internal_test=True)

    print("\n[normal Clients workspace]")
    listed = {c["id"]: c for c in ada.get("/clients").json()["clients"]}
    check("a retired internal-test client is hidden", retired_only not in listed)
    check("it stays hidden in a search that matches it",
          retired_only not in {c["id"] for c in ada.get("/clients", params={"q": "retired"}).json()["clients"]})
    check("its record and history stay readable at /clients/{id}",
          ada.get(f"/clients/{retired_only}").status_code == 200)
    check("an internal-test client with an active engagement stays listed, marked internal_test",
          mixed in listed and listed[mixed]["internal_test"] is True)
    check("an internal-test client with no engagement yet stays listed", fresh in listed)
    check("real clients stay listed, marked real", {real, bare} <= set(listed)
          and listed[real]["internal_test"] is False)
    check("engagement_count counts active engagements only (real 2, mixed 1 of 2, bare 0)",
          listed[real]["engagement_count"] == 2 and listed[mixed]["engagement_count"] == 1
          and listed[bare]["engagement_count"] == 0)
    check("the real client's card data is intact (city, country, contact)",
          (listed[real]["city"], listed[real]["country"], listed[real]["contact_name"])
          == ("Denver", "USA", "Pat Lee"))
    chooser = {c["id"] for c in ada.get("/clients", params={"internal_test": "true"}).json()["clients"]}
    check("the Internal Test chooser lists active and brand-new internal-test clients, not the retired one",
          chooser == {mixed, fresh})
    check("the chooser hides it in a search too",
          retired_only not in {c["id"] for c in ada.get(
              "/clients", params={"internal_test": "true", "q": "retired"}).json()["clients"]})
    only_real = {c["id"] for c in ada.get("/clients", params={"internal_test": "false"}).json()["clients"]}
    check("?internal_test=false still lists only real clients", only_real == {real, bare})


def card_helper_checks():
    print("\n[card secondary line: web/lib/client-card.ts under Node]")
    node = shutil.which("node")
    check("node is available to run the helper", node is not None)
    if node is None:
        return
    src = open(CARD_HELPER).read()
    js, n = re.subn(r"^(import type|type) .*\n", "", src, flags=re.M)
    js, m = re.subn(r"export function clientCardDetails\(c: CardFields\): string\[\]",
                    "function clientCardDetails(c)", js)
    check("the helper keeps the shape this check strips (two type lines, one signature)",
          n == 2 and m == 1)
    cases = {
        "full": {"city": "Denver", "country": "USA", "contact_name": "Pat Lee", "engagement_count": 2},
        "one": {"city": None, "country": "Canada", "contact_name": None, "engagement_count": 1},
        "empty": {"city": None, "country": None, "contact_name": None, "engagement_count": 0},
        "contact": {"city": "", "country": None, "contact_name": "Sam Roe", "engagement_count": 0},
    }
    script = js + f"\nconst cases = {json.dumps(cases)};\n" + \
        "console.log(JSON.stringify(Object.fromEntries(Object.entries(cases)" \
        ".map(([k, v]) => [k, clientCardDetails(v)]))));\n"
    r = subprocess.run([node, "-e", script], capture_output=True, text=True)
    out = json.loads(r.stdout) if r.returncode == 0 else {}
    check("the helper runs", r.returncode == 0)
    check("full card: location, contact, '2 active engagements', in that order",
          out.get("full") == ["Denver, USA", "Pat Lee", "2 active engagements"])
    check("singular: '1 active engagement'; a missing city leaves just the country",
          out.get("one") == ["Canada", "1 active engagement"])
    check("nothing known: an empty line, not 'No location' or '0 engagements'", out.get("empty") == [])
    check("missing location omitted; zero active engagements shows no count",
          out.get("contact") == ["Sam Roe"])
    joined = json.dumps(out)
    check("no placeholder or zero-count copy in any case",
          not re.search(r"No location|No contact|\b0 (active )?engagements?", joined))


def page_checks():
    print("\n[Clients page]")
    page = open(CLIENTS_PAGE).read()
    check("the page uses the tested helper", "clientCardDetails(c)" in page
          and 'from "@/lib/client-card"' in page)
    check("no placeholder copy and no raw engagement count on the page",
          "No location" not in page and "No contact" not in page and "engagement_count" not in page)
    check("the empty state reads 'No active clients yet.'",
          '"No active clients yet."' in page and "No clients yet" not in page)
    check("the secondary line is omitted when empty", "details.length > 0 &&" in page)
    check("the Internal Test badge sits inline beside the name (no full-width bar)",
          re.search(r'<span className="flex flex-wrap items-center gap-2">\s*<span[^>]*>\{c\.organization_label\}'
                    r"</span>\s*\{c\.internal_test && <InternalTestBadge />\}", page) is not None)
    new_eng = open(os.path.join(REPO_ROOT, "web", "app", "(workspace)", "engagements", "new", "page.tsx")).read()
    check("the new-engagement form preselects an opened internal test client only if the chooser offers it",
          "/clients?internal_test=true" in new_eng
          and "testClients.some((c) => c.id === opened.id) ? opened.id" in new_eng)
    service = open(os.path.join(REPO_ROOT, "peak", "workspace", "service.py")).read()
    searched = re.search(r"def list_clients.*?or_\((.*?)\)\)", service, re.S).group(1)
    check("the search placeholder names exactly the searched fields (company, city, contact)",
          "Search by company, city or contact" in page
          and all(f in searched for f in ("organization_label", "city", "contact_name")))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        print("[setup: temporary SQLite at head]")
        api_checks(build(tmp))
    card_helper_checks()
    page_checks()
    print(f"\nRESULT: {'PASS' if not _failures else 'FAIL'} ({len(_failures)} failure(s))")
    return 1 if _failures else 0


if __name__ == "__main__":
    sys.exit(main())

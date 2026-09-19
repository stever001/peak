#!/usr/bin/env python3
"""Phase 204 — initialize the discovery question pool (explicit, idempotent).

Inserts each question in ``peak.workspace.initial_questions.INITIAL_QUESTIONS`` once, through the
normal workspace path (``discovery.create_question``), keyed by ``seed_key``. Entries whose
``seed_key`` already exists are skipped and reported, never overwritten, so the tool is safe to run
again and never re-imposes a question a consultant has edited or deactivated. Branches are resolved
from ``seed_key`` to the stored question id. Nothing here is client data, and no answer, interview or
observation is created.

It is dry-run unless ``--execute`` is passed. Targets follow ``tools/bootstrap_admin.py``: local
SQLite or ``peak_lab`` by default. Production requires ``--production`` plus
``PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM=1`` and a production-marked runtime URL, and **is not
authorized in Phase 204**. The application never runs this at startup.

Exit status: 0 dry run or success; 1 refused or failed; 2 configuration error.
"""

from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

PRODUCTION_CONFIRM_ENV = "PEAK_PRODUCTION_DISCOVERY_INIT_CONFIRM"


def plan(session_factory):
    """(to_create, already_present) seed keys, in pool order."""
    from sqlalchemy import select

    from peak.db.models import DiscoveryQuestion
    from peak.workspace.initial_questions import INITIAL_QUESTIONS

    with session_factory() as session:
        present = set(session.scalars(select(DiscoveryQuestion.seed_key)
                                      .where(DiscoveryQuestion.seed_key.isnot(None))))
    keys = [q["key"] for q in INITIAL_QUESTIONS]
    return [k for k in keys if k not in present], [k for k in keys if k in present]


def initialize(session_factory) -> dict:
    """Insert every missing seed question; return counts. Idempotent."""
    from sqlalchemy import select

    from peak.db.models import DiscoveryQuestion
    from peak.workspace import discovery
    from peak.workspace.initial_questions import INITIAL_QUESTIONS

    to_create, present = plan(session_factory)
    created = 0
    for index, item in enumerate(INITIAL_QUESTIONS):
        if item["key"] not in to_create:
            continue
        data = {"prompt": item["prompt"], "category": item["category"],
                "answer_type": item["type"], "display_order": (index + 1) * 10}
        if item.get("choices"):
            data["choices"] = list(item["choices"])
        if item.get("branch"):
            parent_key, operator, value = item["branch"]
            with session_factory() as session:
                parent_id = session.scalar(select(DiscoveryQuestion.id)
                                           .where(DiscoveryQuestion.seed_key == parent_key))
            if parent_id is None:
                raise RuntimeError(f"branch parent {parent_key} missing for {item['key']}")
            data["branch"] = {"question_id": parent_id, "operator": operator, "value": value}
        discovery.create_question(session_factory, data, seed_key=item["key"])
        created += 1
    return {"created": created, "already_present": len(present)}


def main(argv=None, session_factory=None) -> int:
    parser = argparse.ArgumentParser(description="Initialize the discovery question pool.")
    parser.add_argument("--execute", action="store_true", help="write (default is a dry run)")
    parser.add_argument("--production", action="store_true",
                        help=f"target production (also requires {PRODUCTION_CONFIRM_ENV}=1)")
    args = parser.parse_args(argv)

    if session_factory is None:
        from bootstrap_admin import target_label

        from peak.db.session import create_session_factory, get_runtime_database_url

        try:
            label = target_label(get_runtime_database_url(), production=args.production,
                                 confirm=os.environ.get(PRODUCTION_CONFIRM_ENV, ""))
        except RuntimeError as exc:
            print(f"REFUSED: {exc}")
            return 2
        if label is None:
            print("REFUSED: without --production only local SQLite or peak_lab is accepted; "
                  f"--production needs {PRODUCTION_CONFIRM_ENV}=1 and a production runtime URL.")
            return 1
        session_factory = create_session_factory()
    else:
        label = "injected"

    print(f"target: {label}")
    to_create, present = plan(session_factory)
    if not args.execute:
        print(f"DRY-RUN OK: would create {len(to_create)} question(s); "
              f"{len(present)} already present. Pass --execute to write.")
        return 0
    result = initialize(session_factory)
    print(f"DONE: created {result['created']} question(s); "
          f"{result['already_present']} already present (left unchanged).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Durable schema-history checks shared by the validation harnesses (Phase 121).

Phases 39–90 asserted the schema as it stood when each was written — "exactly 14 migrations",
"014 is the newest", "exactly 18 tables", "no migration 015" — so the first legitimate schema change
(Phase 201's ``015_consultants``) failed all of them at once. That is the freeze
docs/PHASE91_DRIFT_TEST_SPRAWL_PARALLEL_WORKFLOW_REVIEW.md predicted. The facts those checks were
protecting are historical and never expire; these helpers state them in that form:

- the migration history is one linear chain with exactly one head;
- a historical revision still sits at its original position in that chain, and the current head
  descends from it;
- every table that existed at a historical baseline is still declared.

Plus the authoring-time gate from Phase 67 (Phase 91, recommendation 3): a claim about what *one
phase* changed ("Phase 65 adds no migration", "models.py was not modified by this phase") holds
only while that phase's own harness is uncommitted. Once it has landed, the commit history is the
record, and applying the claim to later phases' work is the freeze, not the invariant.

Stdlib only. It reads files and runs read-only ``git log``; it imports no application code.
"""

from __future__ import annotations

import os
import re
import subprocess
from typing import Dict, Iterable, List, Optional

#: The tables that existed when the Alembic head was ``014_engagement_classification`` — a
#: historical fact, used only as a required subset. Later phases may add tables.
TABLES_AT_014 = (
    "clients", "engagements", "engagement_records", "evidence_references",
    "source_system_references", "financial_impact_estimates", "resolver_capsule_records",
    "review_records", "agent_run_records", "capsule_publication_candidates",
    "source_ingestion_records", "agent_task_queue_records", "review_bundle_records",
    "internal_reviewer_decision_records", "intake_note_records",
    "internal_assessment_report_drafts", "internal_report_review_packets",
    "internal_report_review_packet_decisions",
)

_REVISION_RE = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN_RE = re.compile(r'^down_revision\s*=\s*(None|["\']([^"\']+)["\'])', re.MULTILINE)
_TABLENAME_RE = re.compile(r'__tablename__\s*=\s*["\']([^"\']+)["\']')


def _revisions(repo_root: str) -> Optional[Dict[str, Optional[str]]]:
    """``{revision: down_revision}`` for every migration file, or ``None`` if any is unparseable."""
    versions = os.path.join(repo_root, "alembic", "versions")
    graph: Dict[str, Optional[str]] = {}
    for name in sorted(os.listdir(versions)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(versions, name), encoding="utf-8") as fh:
            src = fh.read()
        rev, down = _REVISION_RE.search(src), _DOWN_RE.search(src)
        if rev is None or down is None or rev.group(1) in graph:
            return None
        graph[rev.group(1)] = down.group(2)  # None for the root
    return graph


def migration_chain(repo_root: str) -> Optional[List[str]]:
    """Revisions from root to head, or ``None`` unless history is one linear chain, one head."""
    graph = _revisions(repo_root)
    if not graph:
        return None
    children: Dict[Optional[str], List[str]] = {}
    for rev, down in graph.items():
        children.setdefault(down, []).append(rev)
    if len(children.get(None, [])) != 1 or any(len(v) > 1 for v in children.values()):
        return None  # several roots, or a branch point (more than one head)
    chain = [children[None][0]]
    while chain[-1] in children:
        chain.append(children[chain[-1]][0])
    return chain if len(chain) == len(graph) else None  # a revision off the chain


def history_intact(repo_root: str, revision: str, position: int) -> bool:
    """History is linear and ``revision`` is still migration number ``position`` (1-based)."""
    chain = migration_chain(repo_root)
    return chain is not None and len(chain) >= position and chain[position - 1] == revision


def head_descends_from(repo_root: str, revision: str) -> bool:
    """``revision`` is in the single linear history, so the current head is it or descends from it."""
    chain = migration_chain(repo_root)
    return chain is not None and revision in chain


def verifier_head_at_or_after(repo_root: str, verifier_src: str, revision: str) -> bool:
    """The production verifier's pinned head is ``revision`` or a later revision in the history.

    The verifier's pin moves only after a migration is really applied to production (Phases 58
    and 203), so harnesses assert the durable fact — it never points before ``revision`` or off
    the chain — rather than one literal value.
    """
    m = re.search(r'^EXPECTED_ALEMBIC_HEAD = "([^"]+)"', verifier_src, re.MULTILINE)
    chain = migration_chain(repo_root) or []
    return (m is not None and revision in chain and m.group(1) in chain
            and chain.index(m.group(1)) >= chain.index(revision))


def declared_tables(models_src: str) -> List[str]:
    return _TABLENAME_RE.findall(models_src)


def missing_tables(present: Iterable[str], required: Iterable[str] = TABLES_AT_014) -> List[str]:
    present = set(present)
    return [t for t in required if t not in present]


def phase_never_committed(repo_root: str, rel: str) -> bool:
    """True while ``rel`` (a phase's own harness) has no commit yet — the phase is being authored."""
    out = subprocess.run(["git", "-C", repo_root, "log", "-1", "--format=%H", "--", rel],
                         capture_output=True, text=True)
    return not out.stdout.strip()

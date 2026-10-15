"""Client presentation of release-package renditions (Phase 213; ARTIFACT_LIFECYCLE.md AL36, AL37, AL50).

A **presentation layer, not a composer**. It changes how the one canonical ``FinalReport`` is
presented in the web and DOCX renditions of a release package, and nothing about what it says:

- every section, in the canonical order, with every finding, recommendation, statement and limitation
  the version holds;
- **no internal-draft status**: no status table, no draft banner or footer, no "not client-facing" /
  "not approved for client use" wording, no "internal only; requires human review" line;
- **no internal identifiers**: record, engagement and client ids are left out, and an evidence or
  finding id inside a fixed composer sentence is replaced by its position label ("Evidence item 2",
  "Finding 2");
- **a business title**: the engagement's name, never "Final report" (AL37); no version history.

The only wording it changes is listed in :data:`CLIENT_TEXT` and :data:`_CLIENT_PATTERNS`: exact
fixed sentences the composer itself writes about the draft's internal status. Consultant-entered and
evidence text is never reworded; ids in it are only relabelled. :func:`client_presentation_problems`
then checks the stored renditions for Peak-owned internal material only (exact internal status text,
the internal title, Peak-generated ids), never for ordinary words in business content; a package
whose renditions fail it is not releasable.

The internal presentation (:data:`INTERNAL`) is exactly the Phase 209 DOCX presentation, unchanged.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .final_report import (
    BOUNDARY_STATEMENTS,
    REPORT_STATUS_TEXT,
    SECTION_RECOMMENDATIONS,
    SECTION_TITLES,
    FinalReport,
)
from .internal_assessment import _trace_line

INTERNAL_FOOTER_TEXT = "Internal draft · Not client-facing · Requires consultant review"
INTERNAL_TITLE = "Final report"
#: The internal presentation's status line under each recommendation.
INTERNAL_RECOMMENDATION_LINE = "Internal only; requires human review"

#: Exact composer sentences about the draft's internal status, and their client presentation.
#: ``None`` leaves the sentence out. Nothing else is reworded.
CLIENT_TEXT: Dict[str, Optional[str]] = {
    BOUNDARY_STATEMENTS[2]: ("Recommendations appear only for evidence-backed findings that meet "
                             "the recommendation eligibility rules."),
    BOUNDARY_STATEMENTS[3]: None,
}

#: The composer's fixed count sentences that name recommendations "internal".
_CLIENT_PATTERNS: Tuple[Tuple["re.Pattern[str]", str], ...] = (
    (re.compile(r"^(Evidence-backed findings: \d+, of which \d+ targeted by a review and \d+ "
                r"eligible for) an internal recommendation\.$"), r"\1 a recommendation."),
    (re.compile(r"^Internal recommendations: (\d+) \(status: ([\w-]+)\)\.$"),
     r"Recommendations: \1 (status: \2)."),
)

CLIENT_SECTION_TITLES = {SECTION_RECOMMENDATIONS: "Recommendations (evidence-backed only)"}

#: Peak-owned internal presentation material: exact fixed text that only Peak's composer or the
#: internal presentation emits (AL36, AL50). The check looks for these, never for ordinary words, so
#: business content that happens to say "final report" or "internal" is never rejected.
PEAK_INTERNAL_MARKERS: Tuple[str, ...] = (
    REPORT_STATUS_TEXT,
    INTERNAL_FOOTER_TEXT,
    INTERNAL_RECOMMENDATION_LINE,
    BOUNDARY_STATEMENTS[2],
    BOUNDARY_STATEMENTS[3],
    SECTION_TITLES[SECTION_RECOMMENDATIONS],
)
#: The composer's own count templates that name recommendations "internal".
PEAK_INTERNAL_PATTERNS: Tuple["re.Pattern[str]", ...] = tuple(
    re.compile(p.pattern.strip("^$")) for p, _ in _CLIENT_PATTERNS)


def _count(values: Sequence[str], noun: str) -> str:
    return f"{len(values)} {noun}" + ("" if len(values) == 1 else "s") if values else "none"


class Presentation:
    """How one report is presented. ``client=False`` is the unchanged internal presentation."""

    def __init__(self, report: Optional[FinalReport] = None, client: bool = False):
        self.client = client
        self.labels: Dict[str, str] = {}
        if client and report is not None:
            for n, f in enumerate(report.evidence_findings.findings, start=1):
                self.labels.setdefault(f.finding_id, f"Finding {n}")
            evidence = [f.evidence_id for f in report.evidence_findings.findings]
            evidence += [e.get("evidence_id") for e in report.evidence_findings.excluded_evidence]
            n = 0
            for evidence_id in evidence:
                if evidence_id and evidence_id not in self.labels:
                    n += 1
                    self.labels[evidence_id] = f"Evidence item {n}"

    # --- text ------------------------------------------------------------------------------

    def text(self, value: str) -> Optional[str]:
        """A fixed or recorded sentence as presented; ``None`` to leave it out."""
        if not self.client:
            return value
        if value in CLIENT_TEXT:
            return CLIENT_TEXT[value]
        for pattern, replacement in _CLIENT_PATTERNS:
            if pattern.match(value):
                return pattern.sub(replacement, value)
        for identifier in sorted(self.labels, key=len, reverse=True):
            value = value.replace(identifier, self.labels[identifier])
        return value

    def texts(self, values: Iterable[str]) -> List[str]:
        out = [self.text(v) for v in values]
        return [v for v in out if v is not None]

    def label(self, identifier: Optional[str]) -> str:
        return self.labels.get(identifier or "", "")

    # --- structure ---------------------------------------------------------------------------

    def section_title(self, report: FinalReport, key: str) -> str:
        if self.client and key in CLIENT_SECTION_TITLES:
            return CLIENT_SECTION_TITLES[key]
        return report.section_titles[key]

    def title(self, report: FinalReport) -> str:
        if not self.client:
            return INTERNAL_TITLE
        return report.executive_overview.engagement_label or "Engagement report"

    def subtitle(self, report: FinalReport) -> str:
        o = report.executive_overview
        if not self.client:
            return f"{o.client_name or 'Client not recorded'} · {o.engagement_label or 'Untitled engagement'}"
        return o.client_name or ""

    @property
    def status_block(self) -> bool:
        """The internal status table and draft notice. Never in a client rendition."""
        return not self.client

    def footer(self, report: FinalReport) -> str:
        if not self.client:
            return INTERNAL_FOOTER_TEXT
        o = report.executive_overview
        return " · ".join(p for p in (o.client_name, o.engagement_label) if p)

    def overview_rows(self, report: FinalReport) -> List[Tuple[str, str]]:
        o = report.executive_overview
        if not self.client:
            return [("Engagement", f"{o.engagement_label or 'Untitled engagement'} ({o.engagement_id})"),
                    ("Client", (o.client_name or "not recorded")
                     + (f" ({o.client_id})" if o.client_id else ""))]
        return [("Engagement", o.engagement_label or "Untitled engagement"),
                ("Client", o.client_name or "not recorded")]

    def trace(self, trace) -> str:
        """Where discovery material came from: people and questions, never record ids."""
        if not self.client:
            return _trace_line(trace)
        parts = [f"interview with {trace.interviewee_name}" if trace.interviewee_name
                 else "recorded outside an interview"]
        if trace.question_prompt:
            parts.append(f'question "{trace.question_prompt}"')
        if trace.recorded_by:
            parts.append(f"recorded by {trace.recorded_by}")
        return "; ".join(parts)

    def finding_heading(self, index: int, finding) -> str:
        return f"Finding {index}" if self.client else f"Finding {index} — {finding.finding_id}"

    def evidence_rows(self, f) -> List[Tuple[str, str]]:
        if not self.client:
            return [("Evidence", f.evidence_id),
                    ("Source", ", ".join(f.source_reference_ids) or "none recorded"),
                    ("Review status", f.review_status),
                    ("Supporting reviews", ", ".join(f.supporting_review_ids) or "none"),
                    ("Reliability", f.reliability or "not recorded"),
                    ("Claim scope", f.claim_scope or "not recorded"),
                    ("Recommendation eligibility",
                     "eligible" if f.recommendation_eligible else "blocked")]
        return [("Evidence", self.label(f.evidence_id) or "recorded"),
                ("Sources", _count(f.source_reference_ids, "source")),
                ("Review status", f.review_status),
                ("Supporting reviews", _count(f.supporting_review_ids, "review")),
                ("Reliability", f.reliability or "not recorded"),
                ("Claim scope", f.claim_scope or "not recorded"),
                ("Recommendation eligibility",
                 "eligible" if f.recommendation_eligible else "blocked")]

    def recommendation_details(self, rec) -> List[str]:
        if not self.client:
            return [f"For finding {rec.finding_id}; evidence {', '.join(rec.supporting_evidence_ids)}",
                    INTERNAL_RECOMMENDATION_LINE]
        evidence = [self.label(e) for e in rec.supporting_evidence_ids if self.label(e)]
        line = f"For {self.label(rec.finding_id) or 'its finding'}"
        return [line + (f"; {', '.join(evidence).lower()}" if evidence else "")]

    def docx_file_name(self, report: FinalReport, internal_name: str) -> str:
        if not self.client:
            return internal_name
        o = report.executive_overview
        parts = [p for p in (_slug(o.client_name), _slug(o.engagement_label)) if p]
        return ("-".join(parts) or "report") + ".docx"


def _slug(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")[:60]


INTERNAL = Presentation()


def client_presentation(report: FinalReport) -> Presentation:
    return Presentation(report, client=True)


# --------------------------------------------------------------------------- compliance


def _identifiers(content, out: set) -> set:
    """Every id-like value in the canonical content: keys ending ``_id`` or ``_ids``."""
    if isinstance(content, dict):
        for key, value in content.items():
            if key.endswith("_id") and isinstance(value, str) and value:
                out.add(value)
            elif key.endswith("_ids") and isinstance(value, list):
                out.update(v for v in value if isinstance(v, str) and v)
            else:
                _identifiers(value, out)
    elif isinstance(content, list):
        for value in content:
            _identifiers(value, out)
    return out


def rendition_text(rendition_type: str, data: bytes) -> str:
    """The visible text of a stored rendition (tags dropped, entities decoded)."""
    if rendition_type == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = " ".join(z.read(n).decode("utf-8") for n in z.namelist()
                           if n == "word/document.xml" or re.match(r"word/footer\d*\.xml$", n))
        markup = xml
    else:
        markup = data.decode("utf-8")
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def _title_text(rendition_type: str, data: bytes) -> str:
    """The document title element: the HTML ``<h1>``, or the DOCX paragraph styled ``Title``."""
    if rendition_type == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        m = re.search(r'<w:pStyle w:val="Title"/></w:pPr>(.*?)</w:p>', xml)
    else:
        m = re.search(r"<h1>(.*?)</h1>", data.decode("utf-8"), re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(1))).split()) if m else ""


def client_presentation_problems(renditions: Dict[str, bytes], content: dict,
                                 internal_ids: Iterable[str] = ()) -> List[str]:
    """Why these renditions are not client-facing (AL36, AL37, AL50); empty when they are.

    Checks the stored bytes for **Peak-owned internal material only**:

    - an exact internal status sentence, footer or label (:data:`PEAK_INTERNAL_MARKERS`) or a
      composer count template naming internal recommendations (:data:`PEAK_INTERNAL_PATTERNS`);
    - the internal document title ("Final report") as the title element, unless that is the
      engagement's own name;
    - a Peak-generated identifier: any id-like value in the version's content, or the package,
      version and artifact ids and hashes.

    Business content (consultant-, evidence- or client-authored text) is never searched for words
    and never altered: a North Star or finding that says "final report" or "internal" is fine.
    """
    ids = _identifiers(content, set()) | {i for i in internal_ids if i}
    engagement_label = (content.get("executive_overview") or {}).get("engagement_label")
    problems = []
    for kind in sorted(renditions):
        text = rendition_text(kind, renditions[kind])
        for marker in PEAK_INTERNAL_MARKERS:
            if " ".join(marker.split()) in text:
                problems.append(f"{kind}: contains internal presentation text “{marker[:48]}…”")
        for pattern in PEAK_INTERNAL_PATTERNS:
            if pattern.search(text):
                problems.append(f"{kind}: contains an internal count line")
        if _title_text(kind, renditions[kind]) == INTERNAL_TITLE != engagement_label:
            problems.append(f"{kind}: uses the internal title “{INTERNAL_TITLE}”")
        if any(identifier in text for identifier in ids):
            problems.append(f"{kind}: contains an internal identifier")
    return problems

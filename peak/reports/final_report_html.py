"""Final Report web rendition (Phase 213) — a composed FinalReport in, one static HTML document out.

The web counterpart of the Phase 209 DOCX renderer, for **release packages**: the HTML is rendered
once and its exact bytes are stored with the package, so the web artifact an approver reviews is the
web artifact that is released, whatever later happens to application rendering code (AL47).

**It renders; it never composes** (Contract C7, AL34). It reads only the report object and the fixed
constants its modules already define, section by section in :data:`SECTION_ORDER`, with the same
content as the DOCX renderer. There is no ``peak.db`` import, no connection and no re-query.

``presentation`` decides presentation only, exactly as for the DOCX: release packages pass the
client presentation (``peak.reports.release_presentation``), so neither rendition carries internal
status wording or identifiers (AL36, AL50).

**Static and self-contained.** One document with inline CSS: no script, no external stylesheet,
font, image or link, so the stored bytes display the same anywhere. There are no timestamps, so the
same report always yields the same bytes.
"""

from __future__ import annotations

from html import escape
from typing import Iterable, List, Optional, Sequence

from .discovery_assessment import DISCOVERY_NOT_EVIDENCE_TEXT, NO_DISCOVERY_TEXT
from .final_report import (
    NO_RECOMMENDATIONS_TEXT,
    REPORT_STATUS_TEXT,
    SECTION_DISCOVERY_SUMMARY,
    SECTION_EVIDENCE_FINDINGS,
    SECTION_EXECUTIVE_OVERVIEW,
    SECTION_LIMITATIONS,
    SECTION_LOW_HANGING_FRUIT,
    SECTION_ORDER,
    SECTION_RECOMMENDATIONS,
    FinalReport,
    _level,
)
from .final_report_docx import MATERIAL_LABELS
from .internal_assessment import (
    EVIDENCE_MATERIAL_LABEL,
    NO_DISCOVERY_FINDINGS_TEXT,
    NO_FINDINGS_TEXT,
    NO_LOW_HANGING_FRUIT_TEXT,
    NO_NORTH_STAR_TEXT,
    NO_STATEMENT_TEXT,
)
from .release_presentation import INTERNAL, Presentation

HTML_MEDIA_TYPE = "text/html; charset=utf-8"

_STYLE = (
    "body{margin:0;background:#fff;color:#1f2933;font:16px/1.55 Calibri,Arial,sans-serif}"
    "main{max-width:52rem;margin:0 auto;padding:2rem 1.25rem 3rem}"
    "h1{color:#1f4e79;font-size:2rem;margin:0 0 .25rem}"
    "h2{color:#1f4e79;font-size:1.4rem;margin:2.25rem 0 .5rem;border-bottom:1px solid #c9d1d9;"
    "padding-bottom:.25rem}"
    "h3{font-size:1.1rem;margin:1.5rem 0 .4rem}h4{font-size:1rem;margin:1.1rem 0 .3rem}"
    ".subtitle{color:#52606d;font-size:1.15rem;margin:0 0 1.5rem}"
    ".material{color:#52606d;font-style:italic;font-size:.9rem;margin:0 0 .75rem}"
    ".notice{border-left:4px solid #c9d1d9;padding:.5rem .9rem;background:#f5f7fa}"
    ".detail{color:#52606d;font-size:.9rem;margin:.1rem 0 .1rem 1.25rem}"
    ".north-star{font-size:1.2rem;margin:.25rem 0}"
    "table{border-collapse:collapse;width:100%;margin:.5rem 0 1rem;font-size:.95rem}"
    "th,td{border:1px solid #c9d1d9;padding:.35rem .6rem;text-align:left;vertical-align:top;"
    "overflow-wrap:anywhere}"
    "td:first-child{font-weight:600;width:34%}ul{padding-left:1.25rem}li{margin:.35rem 0}"
    "footer{color:#52606d;font-size:.85rem;border-top:1px solid #c9d1d9;margin-top:3rem;"
    "padding-top:.75rem}"
)


def _e(text: Optional[str]) -> str:
    """Escaped text with line breaks kept."""
    return escape(text or "").replace("\n", "<br>")


def _p(text: str, cls: Optional[str] = None, bold_prefix: Optional[str] = None) -> str:
    attr = f' class="{cls}"' if cls else ""
    prefix = f"<strong>{_e(bold_prefix)}</strong>" if bold_prefix else ""
    return f"<p{attr}>{prefix}{_e(text)}</p>"


def _bullets(items: Iterable[str], empty: str = "None recorded.") -> List[str]:
    items = list(items)
    if not items:
        return [_p(empty, "detail")]
    return ["<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"]


def _item(statement: str, details: Sequence[str]) -> str:
    return (f"<li>{_e(statement)}"
            + "".join(f'<p class="detail">{_e(d)}</p>' for d in details) + "</li>")


def _table(rows: Sequence[Sequence[str]]) -> str:
    body = "".join("<tr>" + "".join(f"<td>{_e(v)}</td>" for v in row) + "</tr>" for row in rows)
    return f"<table><tbody>{body}</tbody></table>"


def _section_heading(report: FinalReport, key: str, pres: Presentation,
                     material: Optional[str] = None) -> List[str]:
    out = [f'<h2 id="{key}">{_e(pres.section_title(report, key))}</h2>']
    if material in MATERIAL_LABELS:
        out.append(_p(MATERIAL_LABELS[material], "material"))
    return out


# --- Sections (same content and order as the Phase 208 Markdown and Phase 209 DOCX) -------------

def _title(report: FinalReport, pres: Presentation) -> List[str]:
    o = report.executive_overview
    out = [f"<h1>{_e(pres.title(report))}</h1>"]
    if pres.subtitle(report):
        out.append(_p(pres.subtitle(report), "subtitle"))
    out.append("<h3>North Star</h3>")
    if o.north_star:
        out.append(_p(o.north_star, "north-star"))
        if o.north_star_context:
            out.append(_p(o.north_star_context))
    else:
        out.append(_p(NO_NORTH_STAR_TEXT, "detail"))
    if pres.status_block:
        out.append(_table([
            ("Status", report.status),
            ("Client-facing", "yes" if report.client_facing else "no"),
            ("Approved for client use", "yes" if report.approved_for_client else "no"),
            ("Requires human review", "yes" if report.requires_human_review else "no"),
        ]))
        out.append(_p(REPORT_STATUS_TEXT, "notice"))
    return out


def _overview(report: FinalReport, pres: Presentation) -> List[str]:
    o = report.executive_overview
    out = _section_heading(report, SECTION_EXECUTIVE_OVERVIEW, pres)
    out.append(_table(pres.overview_rows(report)))
    out.append("<h3>North Star</h3>")
    if o.north_star:
        out.append(_p(o.north_star, "north-star"))
        if o.north_star_context:
            out.append(_p(o.north_star_context))
    else:
        out.append(_p(NO_NORTH_STAR_TEXT, "detail"))
    out.append("<h3>Summary</h3>")
    return out + _bullets(pres.texts(o.summary))


def _discovery(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.discovery_summary
    out = _section_heading(report, SECTION_DISCOVERY_SUMMARY, pres, s.material)
    out += [_p(DISCOVERY_NOT_EVIDENCE_TEXT), "<h3>Interview coverage</h3>"]
    if s.coverage is None:
        out.append(_p(NO_DISCOVERY_TEXT, "detail"))
    else:
        c = s.coverage
        rows = [("Interviews", f"{c.total_sessions} ({c.completed_sessions} completed, "
                               f"{c.in_progress_sessions} in progress)"),
                ("People interviewed", f"{len(c.interviewees)}"
                 + (f" — {', '.join(c.interviewees)}" if c.interviewees else ""))]
        if c.interviewee_titles:
            rows.append(("Roles represented", ", ".join(c.interviewee_titles)))
        rows.append(("Distinct questions answered",
                     f"{c.answered_questions} (of {c.active_questions} active question(s) "
                     f"in the pool)"))
        if c.branching_makes_percentage_ambiguous:
            rows.append(("Questions every interview sees",
                         f"{c.answered_unbranched_questions} of "
                         f"{c.unbranched_active_questions} answered"))
        out.append(_table(rows))
    out.append("<h3>Discovery-derived findings</h3>")
    if not s.findings:
        out.append(_p(NO_DISCOVERY_FINDINGS_TEXT, "detail"))
    else:
        out.append("<ul>" + "".join(
            _item(f.statement, [f"Category: {f.category or 'none recorded'}",
                                f"Where this came from: {pres.trace(f.trace)}"])
            for f in s.findings) + "</ul>")
    out.append("<h3>Discovery limitations</h3>")
    return out + _bullets(pres.texts(s.limitations))


def _low_hanging_fruit(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.low_hanging_fruit
    out = _section_heading(report, SECTION_LOW_HANGING_FRUIT, pres, s.material)
    if not s.groups:
        return out + [_p(NO_LOW_HANGING_FRUIT_TEXT, "detail")]
    out += [_p(s.grouping_note), _p(s.not_ranked_note, "notice")]
    for group in s.groups:
        out.append(f"<h4>{_e(group.label)}</h4>")
        out.append("<ul>" + "".join(
            _item(c.statement, [f"Category: {c.category or 'none recorded'} · "
                                f"Consultant-entered effort: {_level(c.estimated_effort)}; "
                                f"value: {_level(c.estimated_value)}",
                                f"Where this came from: {pres.trace(c.trace)}"])
            for c in group.candidates) + "</ul>")
    return out


def _evidence(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.evidence_findings
    out = _section_heading(report, SECTION_EVIDENCE_FINDINGS, pres, s.material)
    out.append(_p(EVIDENCE_MATERIAL_LABEL))
    if not s.findings:
        out.append(_p(NO_FINDINGS_TEXT, "detail"))
    for index, f in enumerate(s.findings, start=1):
        out += [f"<h3>{_e(pres.finding_heading(index, f))}</h3>",
                _p(f.statement) if f.statement_available else _p(NO_STATEMENT_TEXT, "detail"),
                _table(pres.evidence_rows(f))]
    if s.confidence_notes:
        out.append("<h3>Evidence confidence</h3>")
        out += _bullets(pres.texts(s.confidence_notes))
    return out


def _recommendations(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.recommendations
    out = _section_heading(report, SECTION_RECOMMENDATIONS, pres, s.material)
    if not s.recommendations:
        out.append(_p(NO_RECOMMENDATIONS_TEXT, bold_prefix=f"{s.status.capitalize()}. "))
        reasons = pres.texts(s.blocked_reasons)
        return out + (_bullets(reasons) if reasons else [])
    out.append("<ul>" + "".join(_item(rec.text, pres.recommendation_details(rec))
                                for rec in s.recommendations) + "</ul>")
    return out


def _limitations(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.limitations
    out = _section_heading(report, SECTION_LIMITATIONS, pres)
    out += _bullets(pres.texts(s.boundary_statements))
    out.append("<h3>Evidence limitations</h3>")
    out += _bullets(pres.texts(s.assessment_limitations))
    out.append("<h3>Discovery limitations</h3>")
    return out + _bullets(pres.texts(s.discovery_limitations))


_RENDERERS = {
    SECTION_EXECUTIVE_OVERVIEW: _overview,
    SECTION_DISCOVERY_SUMMARY: _discovery,
    SECTION_LOW_HANGING_FRUIT: _low_hanging_fruit,
    SECTION_EVIDENCE_FINDINGS: _evidence,
    SECTION_RECOMMENDATIONS: _recommendations,
    SECTION_LIMITATIONS: _limitations,
}


def render_final_report_html(report: FinalReport, presentation: Presentation = INTERNAL) -> bytes:
    """Render an already-composed FinalReport as one static HTML document (UTF-8 bytes)."""
    pres = presentation
    title = " — ".join(p for p in (pres.title(report), pres.subtitle(report)) if p)
    body = _title(report, pres)
    for key in SECTION_ORDER:
        body += _RENDERERS[key](report, pres)
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(title)}</title><style>{_STYLE}</style></head>"
            f"<body><main>{''.join(body)}<footer>{_e(pres.footer(report))}</footer></main></body></html>")
    return page.encode("utf-8")

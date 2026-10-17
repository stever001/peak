"""Final Report DOCX export (Phase 209) — a composed FinalReport in, an editable Word document out.

Renders the :class:`~peak.reports.final_report.FinalReport` that Phase 208 already composed. **It
renders; it never composes.** There is no ``peak.db`` import, no connection, no re-query, and no
second report model: every heading, section, finding, recommendation and fixed statement comes from
the report object or the constants its module already defines, in :data:`SECTION_ORDER`. A
recommendation appears here only because it is in ``report.recommendations`` — nothing is filtered,
added or reworded.

**Standard library only.** The document is written as plain WordprocessingML with ``zipfile``, so
Phase 209 adds no dependency. All formatting lives in one ``styles.xml`` (title, headings, body,
material label, notice, detail, bullets, one table style); body paragraphs only name a style. Zip
timestamps are fixed and there is no ``docProps/core.xml`` with a creation time, so the same report
always produces the same bytes.

**The boundaries carry through.** Discovery sections keep the "consultant working material" label,
evidence sections keep the "evidence-backed, governed" label, the low-hanging-fruit section keeps
the Phase 206 display grouping and its not-a-ranking statements, and every page footer says the
document is an internal draft that requires consultant review. See
docs/PHASE209_FINAL_REPORT_DOCX_EXPORT.md.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Iterable, List, Optional, Sequence
from xml.sax.saxutils import escape

from .discovery_assessment import DISCOVERY_NOT_EVIDENCE_TEXT, NO_DISCOVERY_TEXT, basis_label
from .final_report import (
    MATERIAL_DISCOVERY,
    MATERIAL_EVIDENCE,
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
from .internal_assessment import (
    EVIDENCE_MATERIAL_LABEL,
    NO_DISCOVERY_FINDINGS_TEXT,
    NO_FINDINGS_TEXT,
    NO_LOW_HANGING_FRUIT_TEXT,
    NO_NORTH_STAR_TEXT,
    NO_STATEMENT_TEXT,
)
from .release_presentation import INTERNAL, INTERNAL_FOOTER_TEXT, Presentation

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

#: The on-page label for each section's material kind. "report" sections carry none.
MATERIAL_LABELS = {
    MATERIAL_DISCOVERY: "Material: consultant working material — not reviewed evidence",
    MATERIAL_EVIDENCE: "Material: evidence-backed, governed",
}

FOOTER_TEXT = INTERNAL_FOOTER_TEXT

_INK, _MUTED, _BRAND, _RULE = "1F2933", "52606D", "1F4E79", "C9D1D9"
_TABLE_BORDERS = ("<w:tblBorders>"
                  + "".join(f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="{_RULE}"/>'
                            for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
                  + "</w:tblBorders>")
_ZIP_DATE = (2000, 1, 1, 0, 0, 0)  # fixed, so the same report always yields the same bytes
_INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


# --- WordprocessingML fragments -----------------------------------------------------------------

def _runs(text: str) -> str:
    """Text runs with line breaks kept; control characters Word cannot hold are dropped."""
    lines = _INVALID_XML.sub("", text).split("\n")
    return "<w:br/>".join(f'<w:t xml:space="preserve">{escape(line)}</w:t>' for line in lines)


def _p(text: str = "", style: Optional[str] = None, bold_prefix: Optional[str] = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    prefix = f"<w:r><w:rPr><w:b/></w:rPr>{_runs(bold_prefix)}</w:r>" if bold_prefix else ""
    body = f"<w:r>{_runs(text)}</w:r>" if text else ""
    return f"<w:p>{props}{prefix}{body}</w:p>"


def _bullets(items: Iterable[str], empty: str = "None recorded.") -> List[str]:
    items = list(items)
    return [_p(item, "ListBullet") for item in items] if items else [_p(empty, "Detail")]


def _table(rows: Sequence[Sequence[str]], header: Optional[Sequence[str]] = None) -> str:
    """A compact table in the shared ``PeakTable`` style; the first column is the label column."""
    def cell(text: str, bold: bool = False) -> str:
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return (f'<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/></w:tcPr>'
                f'<w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr><w:r>{rpr}{_runs(text)}</w:r>'
                f"</w:p></w:tc>")

    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="PeakTable"/><w:tblW w:w="5000" w:type="pct"/>'
           + _TABLE_BORDERS +  # repeated from the style for readers that ignore table styles
           f'<w:tblLook w:val="{"04A0" if header else "0480"}" w:firstRow="{1 if header else 0}" '
           'w:firstColumn="1" w:noVBand="1"/></w:tblPr>']
    if header:
        out.append('<w:tr><w:trPr><w:tblHeader/></w:trPr>'
                   + "".join(cell(h, True) for h in header) + "</w:tr>")
    for row in rows:
        out.append("<w:tr>" + "".join(cell(v, i == 0 and not header) for i, v in enumerate(row))
                   + "</w:tr>")
    out.append("</w:tbl>")
    return "".join(out) + _p()  # Word needs a paragraph between consecutive tables


def _section_heading(report: FinalReport, key: str, pres: Presentation,
                     material: Optional[str] = None) -> List[str]:
    out = [_p(pres.section_title(report, key), "Heading1")]
    if material in MATERIAL_LABELS:
        out.append(_p(MATERIAL_LABELS[material], "MaterialLabel"))
    return out


# --- Sections (same content and order as the Phase 208 Markdown) --------------------------------
# ``pres`` decides presentation only: the internal draft (default, Phase 209) or a release
# package's client rendition (peak.reports.release_presentation). The content is the same.

def _title_page(report: FinalReport, pres: Presentation) -> List[str]:
    o = report.executive_overview
    out = [_p(pres.title(report), "Title")]
    if pres.subtitle(report):
        out.append(_p(pres.subtitle(report), "Subtitle"))
    out.append(_p("North Star", "Heading3"))
    if o.north_star:
        out.append(_p(o.north_star, "NorthStar"))
        if o.north_star_context:
            out.append(_p(o.north_star_context))
    else:
        out.append(_p(NO_NORTH_STAR_TEXT, "Detail"))
    if pres.status_block:
        out.append(_table([
            ("Status", report.status),
            ("Client-facing", "yes" if report.client_facing else "no"),
            ("Approved for client use", "yes" if report.approved_for_client else "no"),
            ("Requires human review", "yes" if report.requires_human_review else "no"),
        ]))
        out.append(_p(REPORT_STATUS_TEXT, "Notice"))
    out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    return out


def _overview(report: FinalReport, pres: Presentation) -> List[str]:
    o = report.executive_overview
    out = _section_heading(report, SECTION_EXECUTIVE_OVERVIEW, pres)
    out.append(_table(pres.overview_rows(report)))
    out.append(_p("North Star", "Heading2"))
    if o.north_star:
        out.append(_p(o.north_star, "NorthStar"))
        if o.north_star_context:
            out.append(_p(o.north_star_context))
    else:
        out.append(_p(NO_NORTH_STAR_TEXT, "Detail"))
    out.append(_p("Summary", "Heading2"))
    return out + _bullets(pres.texts(o.summary))


def _discovery(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.discovery_summary
    out = _section_heading(report, SECTION_DISCOVERY_SUMMARY, pres, s.material)
    out += [_p(DISCOVERY_NOT_EVIDENCE_TEXT), _p("Interview coverage", "Heading2")]
    if s.coverage is None:
        out.append(_p(NO_DISCOVERY_TEXT, "Detail"))
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
    out.append(_p("Discovery-derived findings", "Heading2"))
    if not s.findings:
        out.append(_p(NO_DISCOVERY_FINDINGS_TEXT, "Detail"))
    for finding in s.findings:
        out += [_p(finding.statement, "ListBullet"),
                _p(f"Category: {finding.category or 'none recorded'}", "Detail"),
                _p(f"Basis: {basis_label(finding.basis)}", "Detail"),
                _p(f"Where this came from: {pres.trace(finding.trace)}", "Detail")]
    out.append(_p("Discovery limitations", "Heading2"))
    return out + _bullets(pres.texts(s.limitations))


def _low_hanging_fruit(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.low_hanging_fruit
    out = _section_heading(report, SECTION_LOW_HANGING_FRUIT, pres, s.material)
    if not s.groups:
        return out + [_p(NO_LOW_HANGING_FRUIT_TEXT, "Detail")]
    out += [_p(s.grouping_note), _p(s.not_ranked_note, "Notice")]
    for group in s.groups:
        out.append(_p(group.label, "Heading3"))
        for candidate in group.candidates:
            out += [_p(candidate.statement, "ListBullet"),
                    _p(f"Category: {candidate.category or 'none recorded'} · "
                       f"Consultant-entered effort: {_level(candidate.estimated_effort)}; "
                       f"value: {_level(candidate.estimated_value)}", "Detail"),
                    _p(f"Basis: {basis_label(candidate.basis)}", "Detail"),
                    _p(f"Where this came from: {pres.trace(candidate.trace)}", "Detail")]
    return out


def _evidence(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.evidence_findings
    out = _section_heading(report, SECTION_EVIDENCE_FINDINGS, pres, s.material)
    out.append(_p(EVIDENCE_MATERIAL_LABEL))
    if not s.findings:
        out.append(_p(NO_FINDINGS_TEXT, "Detail"))
    for index, f in enumerate(s.findings, start=1):
        out += [_p(pres.finding_heading(index, f), "Heading2"),
                _p(f.statement) if f.statement_available else _p(NO_STATEMENT_TEXT, "Detail"),
                _table(pres.evidence_rows(f))]
    if s.confidence_notes:
        out.append(_p("Evidence confidence", "Heading2"))
        out += _bullets(pres.texts(s.confidence_notes))
    return out


def _recommendations(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.recommendations
    out = _section_heading(report, SECTION_RECOMMENDATIONS, pres, s.material)
    if not s.recommendations:
        out.append(_p(NO_RECOMMENDATIONS_TEXT, bold_prefix=f"{s.status.capitalize()}. "))
        return out + ([_p(r, "ListBullet") for r in pres.texts(s.blocked_reasons)])
    for rec in s.recommendations:
        out.append(_p(rec.text, "ListBullet"))
        out += [_p(line, "Detail") for line in pres.recommendation_details(rec)]
    return out


def _limitations(report: FinalReport, pres: Presentation) -> List[str]:
    s = report.limitations
    out = _section_heading(report, SECTION_LIMITATIONS, pres)
    out += _bullets(pres.texts(s.boundary_statements))
    out.append(_p("Evidence limitations", "Heading2"))
    out += _bullets(pres.texts(s.assessment_limitations))
    out.append(_p("Discovery limitations", "Heading2"))
    return out + _bullets(pres.texts(s.discovery_limitations))


_RENDERERS = {
    SECTION_EXECUTIVE_OVERVIEW: _overview,
    SECTION_DISCOVERY_SUMMARY: _discovery,
    SECTION_LOW_HANGING_FRUIT: _low_hanging_fruit,
    SECTION_EVIDENCE_FINDINGS: _evidence,
    SECTION_RECOMMENDATIONS: _recommendations,
    SECTION_LIMITATIONS: _limitations,
}


# --- Package parts ------------------------------------------------------------------------------

def _document_xml(report: FinalReport, pres: Presentation) -> str:
    body = _title_page(report, pres)
    for key in SECTION_ORDER:
        body += _RENDERERS[key](report, pres)
    sect = ('<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter"/>'
            '<w:pgSz w:w="12240" w:h="15840"/>'
            '<w:pgMar w:top="1440" w:right="1260" w:bottom="1440" w:left="1260" '
            'w:header="720" w:footer="600" w:gutter="0"/></w:sectPr>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<w:document {_W} {_R}><w:body>{"".join(body)}{sect}</w:body></w:document>')


def _field(instruction: str) -> str:
    return (f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> {instruction} </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r>'
            f'<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def _footer_xml(text: str) -> str:
    lead = f"{text} · Page " if text else "Page "
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {_W}>'
            f'<w:p><w:pPr><w:pStyle w:val="Footer"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{escape(lead)}</w:t></w:r>{_field("PAGE")}'
            f'<w:r><w:t xml:space="preserve"> of </w:t></w:r>{_field("NUMPAGES")}</w:p></w:ftr>')


_FOOTER_XML = _footer_xml(FOOTER_TEXT)


def _style(style_id: str, name: str, ppr: str = "", rpr: str = "", kind: str = "paragraph",
           based_on: str = "Normal", extra: str = "") -> str:
    based = f'<w:basedOn w:val="{based_on}"/>' if based_on and style_id != "Normal" else ""
    return (f'<w:style w:type="{kind}" w:styleId="{style_id}"><w:name w:val="{name}"/>{based}'
            f'<w:qFormat/>{extra}<w:pPr>{ppr}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')



#: Every format in the document is defined here, once.
_STYLES_XML = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}>'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>'
    f'<w:sz w:val="22"/><w:szCs w:val="22"/><w:color w:val="{_INK}"/><w:lang w:val="en-US"/>'
    '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
    '<w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>'
    '</w:docDefaults>'
    + _style("Normal", "Normal", based_on="")
    + _style("Title", "Title", '<w:spacing w:before="2400" w:after="120"/>',
             f'<w:b/><w:color w:val="{_BRAND}"/><w:sz w:val="56"/><w:szCs w:val="56"/>')
    + _style("Subtitle", "Subtitle", '<w:spacing w:after="600"/>',
             f'<w:color w:val="{_MUTED}"/><w:sz w:val="28"/><w:szCs w:val="28"/>')
    + _style("Heading1", "heading 1",
             '<w:keepNext/><w:spacing w:before="480" w:after="160"/>'
             f'<w:pBdr><w:bottom w:val="single" w:sz="8" w:space="4" w:color="{_BRAND}"/></w:pBdr>'
             '<w:outlineLvl w:val="0"/>',
             f'<w:b/><w:color w:val="{_BRAND}"/><w:sz w:val="34"/><w:szCs w:val="34"/>')
    + _style("Heading2", "heading 2",
             '<w:keepNext/><w:spacing w:before="280" w:after="100"/><w:outlineLvl w:val="1"/>',
             f'<w:b/><w:color w:val="{_INK}"/><w:sz w:val="26"/><w:szCs w:val="26"/>')
    + _style("Heading3", "heading 3",
             '<w:keepNext/><w:spacing w:before="220" w:after="80"/><w:outlineLvl w:val="2"/>',
             f'<w:b/><w:color w:val="{_MUTED}"/><w:sz w:val="23"/><w:szCs w:val="23"/>')
    + _style("NorthStar", "North Star",
             f'<w:spacing w:after="160"/><w:ind w:left="240"/>'
             f'<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="{_BRAND}"/></w:pBdr>',
             '<w:sz w:val="28"/><w:szCs w:val="28"/>')
    + _style("MaterialLabel", "Material label", '<w:spacing w:after="200"/>',
             f'<w:b/><w:caps/><w:color w:val="{_MUTED}"/><w:sz w:val="17"/><w:szCs w:val="17"/>'
             '<w:spacing w:val="10"/>')
    + _style("Notice", "Notice",
             '<w:spacing w:before="120" w:after="200"/>'
             f'<w:pBdr><w:top w:val="single" w:sz="4" w:space="6" w:color="{_RULE}"/>'
             f'<w:left w:val="single" w:sz="4" w:space="6" w:color="{_RULE}"/>'
             f'<w:bottom w:val="single" w:sz="4" w:space="6" w:color="{_RULE}"/>'
             f'<w:right w:val="single" w:sz="4" w:space="6" w:color="{_RULE}"/></w:pBdr>'
             '<w:shd w:val="clear" w:color="auto" w:fill="F4F6F8"/><w:ind w:left="120" w:right="120"/>',
             '<w:sz w:val="20"/><w:szCs w:val="20"/>')
    + _style("ListBullet", "List Bullet",
             '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
             '<w:spacing w:before="80" w:after="40"/><w:ind w:left="360" w:hanging="360"/>')
    + _style("Detail", "Detail", '<w:spacing w:after="40"/><w:ind w:left="360"/>',
             f'<w:color w:val="{_MUTED}"/><w:sz w:val="19"/><w:szCs w:val="19"/>')
    + _style("TableText", "Table Text", '<w:spacing w:before="40" w:after="40"/>',
             '<w:sz w:val="20"/><w:szCs w:val="20"/>')
    + _style("Footer", "footer", '<w:jc w:val="center"/><w:spacing w:after="0"/>',
             f'<w:color w:val="{_MUTED}"/><w:sz w:val="16"/><w:szCs w:val="16"/>')
    + '<w:style w:type="table" w:styleId="PeakTable"><w:name w:val="Peak Table"/>'
      '<w:tblPr>' + _TABLE_BORDERS + '<w:tblCellMar><w:top w:w="40" w:type="dxa"/>'
        '<w:left w:w="100" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/>'
        '<w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
        '<w:tblStylePr w:type="firstCol"><w:tcPr><w:shd w:val="clear" w:color="auto" '
        'w:fill="F4F6F8"/></w:tcPr></w:tblStylePr>'
        '<w:tblStylePr w:type="firstRow"><w:tcPr><w:shd w:val="clear" w:color="auto" '
        'w:fill="E6EBF0"/></w:tcPr></w:tblStylePr></w:style>'
    + '</w:styles>')

_NUMBERING_XML = (
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering {_W}>'
    '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>'
    '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/>'
    '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="360" w:hanging="360"/></w:pPr></w:lvl>'
    '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')

_CONTENT_TYPES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.styles+xml"/>'
    '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.numbering+xml"/>'
    '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-'
    'officedocument.wordprocessingml.footer+xml"/>'
    '</Types>')

_PACKAGE_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/officeDocument" Target="word/document.xml"/></Relationships>')

_DOCUMENT_RELS_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/styles" Target="styles.xml"/>'
    '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/numbering" Target="numbering.xml"/>'
    '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
    'relationships/footer" Target="footer1.xml"/></Relationships>')


def render_final_report_docx(report: FinalReport, presentation: Presentation = INTERNAL) -> bytes:
    """Render an already-composed FinalReport as DOCX bytes. Deterministic; nothing is stored.

    ``presentation`` defaults to the internal draft. A release package passes the client
    presentation (``peak.reports.release_presentation``), which changes presentation only.
    """
    parts = (("[Content_Types].xml", _CONTENT_TYPES_XML),
             ("_rels/.rels", _PACKAGE_RELS_XML),
             ("word/_rels/document.xml.rels", _DOCUMENT_RELS_XML),
             ("word/document.xml", _document_xml(report, presentation)),
             ("word/styles.xml", _STYLES_XML),
             ("word/numbering.xml", _NUMBERING_XML),
             ("word/footer1.xml", _footer_xml(presentation.footer(report))
                                   if presentation.client else _FOOTER_XML))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, xml in parts:
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, xml.encode("utf-8"))
    return buffer.getvalue()


def _slug(value: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")[:60]


def final_report_docx_filename(report: FinalReport) -> str:
    """An ASCII-safe attachment name from the client and engagement, e.g.
    ``final-report-acme-logistics-inventory-review.docx``."""
    o = report.executive_overview
    parts = [p for p in (_slug(o.client_name), _slug(o.engagement_label or o.engagement_id)) if p]
    return "-".join(["final-report", *parts]) + ".docx"

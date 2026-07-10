#!/usr/bin/env python3
"""Synthetic fixture builders for validation.

These functions build **clearly synthetic**, minimal, schema-conforming objects
entirely in memory. They are NOT stored data artifacts and are NOT derived from any
client data. Validation harnesses call these builders, write the results to a
temporary directory (auto-deleted), validate them against the schemas, and discard
them. Nothing here is committed as data.

Synthetic marker: every id/label uses the `synthetic` marker (e.g.
`intake_synthetic_demo`, `client_synthetic`) so a reader can never mistake it for a
real record. See docs/FIXTURE_STRATEGY.md.
"""

from __future__ import annotations

# A fixed synthetic timestamp/date — arbitrary, not tied to anything real.
_TS = "2020-01-01T00:00:00Z"
_DATE = "2020-01-01"
INTAKE_ID = "intake_synthetic_demo"


def synthetic_client_intake() -> dict:
    return {
        "intake_id": INTAKE_ID,
        "created_at": _TS,
        "created_by": "consultant_synthetic",
        "client_profile": {
            "organization_label": "client_synthetic",
            "organization_type": "distributor",
            "size_indicator": "medium",
            "locations_count_indicator": "few",
            "geographies": ["synthetic_region"],
        },
        "industry": "synthetic industry",
        "operating_model": "synthetic make-to-stock distribution",
        "inventory_environment": {
            "product_categories": ["category_a", "category_b"],
            "storage_types": ["racked", "bulk"],
            "sku_count_indicator": "thousands",
            "throughput_indicator": "moderate",
            "inventory_value_indicator": "high",
        },
        "known_systems": [
            {"name": "ERP", "category": "ERP", "role": "system of record", "notes": "synthetic"},
        ],
        "stated_pain_points": [
            {
                "description": "synthetic pain point",
                "impact_indicator": "high",
                "evidence_references": ["evid_synthetic_1"],
            },
        ],
        "stakeholders": [
            {"role": "operations_manager", "anonymized_label": "stakeholder_synthetic_1", "involvement": "sponsor"},
        ],
        "urgency": {"level": "high", "business_trigger": "synthetic trigger"},
        "available_data_sources": [
            {"name": "synthetic export", "type": "system_export", "availability": "on_request"},
        ],
        "initial_scope_hypothesis": "synthetic hypothesis",
        "first_billing_tranche_objective": "synthetic objective",
        "assessment_readiness": {"status": "partially_ready", "blockers": [], "notes": "synthetic"},
        "evidence_references": ["evid_synthetic_1"],
        "consultant_notes": "synthetic fixture — not real client data",
    }


def synthetic_evidence_reference() -> dict:
    return {
        "evidence_id": "evid_synthetic_1",
        "evidence_type": "interview_statement",
        "source_type": "stakeholder",
        "collection_method": "interview",
        "collected_at": _TS,
        "collected_by": "consultant_synthetic",
        "related_object_ids": [INTAKE_ID],
        "summary": "synthetic evidence summary — not real client data",
        "reliability": "medium",
        "confidence_notes": "synthetic",
        "access_notes": "synthetic",
        "sensitive_data_flag": False,
        "consultant_notes": "synthetic fixture",
    }


def synthetic_stakeholder_interview() -> dict:
    return {
        "interview_id": "intv_synthetic_1",
        "related_intake_id": INTAKE_ID,
        "stakeholder_role": "warehouse_lead",
        "stakeholder_label": "stakeholder_synthetic_2",
        "interviewed_at": _TS,
        "interviewer": "consultant_synthetic",
        "topics_covered": ["counting process", "adjustments"],
        "stated_pain_points": [
            {"description": "synthetic claim", "evidence_references": ["evid_synthetic_1"]},
        ],
        "process_claims": [
            {"claim": "synthetic process claim", "workflow_area": "cycle_count", "evidence_references": ["evid_synthetic_1"]},
        ],
        "system_claims": [
            {"claim": "synthetic system claim", "system_name": "ERP", "evidence_references": []},
        ],
        "quantified_impacts": [
            {"description": "synthetic impact", "metric": "hours_per_week", "reported_value": "1-2", "unit": "hours", "evidence_references": ["evid_synthetic_1"]},
        ],
        "contradictions_or_followups": [
            {"description": "synthetic follow-up", "type": "follow_up"},
        ],
        "evidence_references": ["evid_synthetic_1"],
        "consultant_notes": "synthetic fixture",
    }


def synthetic_visual_observation() -> dict:
    return {
        "observation_id": "vobs_synthetic_1",
        "related_intake_id": INTAKE_ID,
        "observed_at": _TS,
        "observed_by": "consultant_synthetic",
        "site_area": "synthetic_area",
        "observation_type": "labeling",
        "description": "synthetic observation — not real client data",
        "operational_implication": "synthetic implication",
        "severity": "high",
        "suggested_follow_up": "synthetic follow-up",
        "evidence_references": ["evid_synthetic_2"],
        "consultant_notes": "synthetic fixture",
    }


def synthetic_workflow_observation() -> dict:
    return {
        "observation_id": "wobs_synthetic_1",
        "related_intake_id": INTAKE_ID,
        "observed_at": _TS,
        "observed_by": "consultant_synthetic",
        "workflow_area": "adjustment",
        "current_state": "synthetic current state",
        "observed_gap": "synthetic gap",
        "business_impact": "synthetic impact",
        "control_risk": {"description": "synthetic control risk", "severity": "high"},
        "potential_quick_win": True,
        "evidence_references": ["evid_synthetic_1"],
        "consultant_notes": "synthetic fixture",
    }


def synthetic_inventory_system_profile() -> dict:
    return {
        "system_profile_id": "isp_synthetic_1",
        "related_intake_id": INTAKE_ID,
        "known_systems": [
            {"name": "ERP", "category": "ERP", "role": "system of record", "notes": "synthetic"},
        ],
        "records_source_of_truth": {"system_name": "ERP", "confidence": "low", "notes": "synthetic"},
        "integrations": [
            {"description": "synthetic integration", "integration_type": "manual", "reliability": "low"},
        ],
        "manual_workarounds": [
            {"description": "synthetic workaround", "workflow_area": "replenishment", "evidence_references": ["evid_synthetic_1"]},
        ],
        "reporting_outputs": [
            {"name": "synthetic report", "purpose": "synthetic", "source_system": "ERP"},
        ],
        "data_quality_concerns": [
            {"description": "synthetic concern", "data_domain": "counts", "severity": "high", "evidence_references": ["evid_synthetic_1"]},
        ],
        "access_status": {"status": "partial", "notes": "synthetic"},
        "evidence_references": ["evid_synthetic_1"],
        "consultant_notes": "synthetic fixture",
    }


# Maps a schema filename stem to its synthetic builder, so a harness can pair each
# schema with a representative synthetic instance without any committed example file.
STANDALONE_BUILDERS = {
    "client-intake": synthetic_client_intake,
    "evidence-reference": synthetic_evidence_reference,
    "stakeholder-interview": synthetic_stakeholder_interview,
    "visual-observation": synthetic_visual_observation,
    "workflow-observation": synthetic_workflow_observation,
    "inventory-system-profile": synthetic_inventory_system_profile,
}


def synthetic_engagement_packet() -> dict:
    """A self-contained synthetic packet: nested evidence_references resolve to the
    declared evidence store, and every related_intake_id matches the intake id."""
    return {
        "packet_id": "pkt_synthetic_fixture",
        "packet_version": "0.0.0-synthetic",
        "created_at": _TS,
        "updated_at": _TS,
        "engagement_label": "Synthetic fixture engagement (test-only, not real client data)",
        "assessment_stage": "discovery",
        "client_intake": synthetic_client_intake(),
        "inventory_system_profile": synthetic_inventory_system_profile(),
        "evidence_references": [
            synthetic_evidence_reference(),
            {
                "evidence_id": "evid_synthetic_2",
                "evidence_type": "photograph",
                "source_type": "site_walk",
                "collection_method": "photograph",
                "collected_at": _TS,
                "collected_by": "consultant_synthetic",
                "related_object_ids": [INTAKE_ID, "vobs_synthetic_1"],
                "summary": "synthetic photograph description — not real client data",
                "reliability": "high",
                "sensitive_data_flag": False,
                "consultant_notes": "synthetic fixture",
            },
        ],
        "stakeholder_interviews": [synthetic_stakeholder_interview()],
        "visual_observations": [synthetic_visual_observation()],
        "workflow_observations": [synthetic_workflow_observation()],
        "packet_metadata": {
            "prepared_by": "consultant_synthetic",
            "consultant_team": ["consultant_synthetic"],
            "engagement_start": _DATE,
            "confidentiality": "internal",
            "source_note": "Synthetic fixture generated at runtime; not stored, not real client data.",
        },
        "validation_notes": [
            {"note": "Synthetic fixture — generated in memory for validation only.", "level": "info"},
        ],
    }

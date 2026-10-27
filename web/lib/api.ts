import "server-only";

import { cache } from "react";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

/** Session cookie shared with the Python API (it signs and verifies the token). */
export const SESSION_COOKIE = "peak_session";

export type Role = "admin" | "consultant";
export type Consultant = { id: string; name: string; email: string; role: Role };

/** Server-only: the Python API base URL. Never exposed to browser JavaScript. */
function apiBaseUrl(): string {
  return process.env.PEAK_API_BASE_URL ?? "http://127.0.0.1:8000";
}

/** Secure cookies everywhere except explicit local-HTTP development. */
export function secureCookies(): boolean {
  return process.env.PEAK_WEB_INSECURE_COOKIE !== "1";
}

/** Call the Python API from the Next.js server, forwarding the session cookie. */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  const headers = new Headers(init.headers);
  if (token) headers.set("cookie", `${SESSION_COOKIE}=${token}`);
  if (init.body) headers.set("content-type", "application/json");
  return fetch(`${apiBaseUrl()}${path}`, { ...init, headers, cache: "no-store" });
}

/**
 * The signed-in consultant, verified by the Python API on every request.
 * Redirects to /login when there is no valid session. Memoized per render pass.
 */
export const requireConsultant = cache(async (): Promise<Consultant> => {
  const res = await apiFetch("/auth/me");
  if (res.status === 401) redirect("/login");
  if (!res.ok) throw new Error(`Peak API /auth/me failed (${res.status})`);
  return (await res.json()).consultant as Consultant;
});

// --- Phase 202: client and engagement workspace ----------------------------------------------

export type KeyPerson = { name: string; role: string | null; email: string | null; phone: string | null };
export type EngagementStatus = "active" | "on_hold" | "closed";

export type ClientSummary = {
  id: string;
  organization_label: string;
  city: string | null;
  country: string | null;
  contact_name: string | null;
  /** Phase 215: an Admin-created internal test client (reserved namespace). */
  internal_test: boolean;
  /** Active (not retired) engagements only. */
  engagement_count: number;
};

/** Phase 215: machine-readable source state; `internal_test` marks test material, never real-client data. */
export type SourceMarker = {
  engagement_classification: "real_client" | "internal_test";
  source_status: "active" | "deleted";
};

export type Engagement = {
  id: string;
  engagement_label: string | null;
  objective: string | null;
  status: string | null;
  current_phase: string | null;
  client: { id: string; name: string | null };
  assigned_consultant: { id: string; name: string | null } | null;
  deleted_at: string | null;
} & SourceMarker;

export type Client = {
  id: string;
  internal_test: boolean;
  organization_label: string;
  description: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  country: string | null;
  contact_name: string | null;
  contact_title: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  key_personnel: KeyPerson[];
  engagements: Engagement[];
};

export type ConsultantOption = { id: string; name: string };

/** GET a workspace resource: 401 -> /login, 404 -> not-found page. */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (res.status === 401) redirect("/login");
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Peak API ${path} failed (${res.status})`);
  return (await res.json()) as T;
}

// --- Phase 204: discovery / interview workflow ------------------------------------------------

export type AnswerType = "short_text" | "long_text" | "yes_no" | "single_choice";
export type Level = "low" | "medium" | "high";

export type Question = {
  id: string;
  prompt: string;
  category: string;
  answer_type: AnswerType;
  choices: string[];
  display_order: number;
  active: boolean;
  branch: { question_id: string; operator: "equals" | "not_equals"; value: string } | null;
  /** Phase 216: seeded Peak Method question, editable only by an Admin. */
  canonical: boolean;
  seed_key: string | null;
  /** Canonical or global (no engagement): created, edited and deactivated only by an Admin. */
  admin_controlled: boolean;
  /** Supplemental-question provenance: the engagement it was added in (asked only there). */
  engagement_id: string | null;
  added_by_consultant_id: string | null;
  rationale: string | null;
  domain: string | null;
  finding_classes: string[];
  created_at: string | null;
  /** Derived, never stored: answers with text, and observations that name the question. */
  usage?: { answered: number; observations: number };
};

/** Phase 216: what a consultant observation rests on. Never makes it evidence. */
export type ObservationBasis = "testimony" | "observed" | "document" | "measured" | "inferred";

export type SessionSummary = {
  id: string;
  interviewee_name: string;
  interviewee_title: string | null;
  status: "in_progress" | "completed";
  conducted_by: string | null;
  started_at: string;
  answered_count: number;
};

export type Observation = {
  id: string;
  engagement_id: string;
  category: string | null;
  observation_text: string;
  low_hanging_fruit: boolean;
  estimated_effort: Level | null;
  estimated_value: Level | null;
  basis: ObservationBasis | null;
  question: { id: string; prompt: string | null; category: string | null } | null;
  session: { id: string; interviewee_name: string } | null;
  recorded_by: string | null;
  created_at: string | null;
};

export type QuestionOption = { id: string; prompt: string; category: string };

export type Discovery = {
  engagement_id: string;
  discovery_enabled: boolean;
  north_star: string | null;
  north_star_context: string | null;
  key_personnel: KeyPerson[];
  sessions: SessionSummary[];
  observations: Observation[];
  questions: QuestionOption[];
};

export type InterviewSession = {
  id: string;
  status: "in_progress" | "completed";
  interviewee_name: string;
  interviewee_title: string | null;
  notes: string | null;
  conducted_by: string | null;
  started_at: string;
  completed_at: string | null;
  engagement: { id: string; name: string | null };
  client: { id: string; name: string | null };
  questions: (Question & { answer: string | null })[];
  history: { question_id: string; prompt: string; answer: string | null }[];
};

// --- Phase 206: internal assessment (read-only, derived) --------------------------------------

/** Where one piece of discovery material came from. Names first; raw ids for detail only. */
export type DiscoveryTrace = {
  session_id: string | null;
  interviewee_name: string | null;
  observation_id: string | null;
  question_id: string | null;
  answer_id: string | null;
  question_prompt: string | null;
  recorded_by: string | null;
  recorded_by_consultant_id: string | null;
};

/**
 * A consultant-recorded discovery finding. Deliberately has no `recommendation_eligible`,
 * `review_status` or `reliability`: those belong to evidence-backed findings only.
 */
export type DiscoveryFinding = {
  finding_id: string;
  statement: string;
  category: string | null;
  source_type: "discovery_observation" | "direct_structured_answer";
  source_ids: string[];
  trace: DiscoveryTrace;
  low_hanging_fruit: boolean;
  estimated_effort: Level | null;
  estimated_value: Level | null;
  basis: ObservationBasis | null;
  status: string;
  internal_only: boolean;
  requires_human_review: boolean;
};

export type LowHangingFruitCandidate = {
  finding_id: string;
  statement: string;
  category: string | null;
  estimated_effort: Level | null;
  estimated_value: Level | null;
  trace: DiscoveryTrace;
  basis: ObservationBasis | null;
  internal_only: boolean;
  requires_human_review: boolean;
};

export type InterviewCoverage = {
  total_sessions: number;
  completed_sessions: number;
  in_progress_sessions: number;
  interviewees: string[];
  interviewee_titles: string[];
  answered_questions: number;
  active_questions: number;
  unbranched_active_questions: number;
  answered_unbranched_questions: number;
  /** True when follow-up branching makes a single pool-wide percentage misleading. */
  branching_makes_percentage_ambiguous: boolean;
  sessions: {
    session_id: string;
    interviewee_name: string;
    interviewee_title: string | null;
    status: string;
    conducted_by: string | null;
    answered_count: number;
  }[];
};

export type DiscoveryAssessmentContext = {
  engagement_id: string | null;
  available: boolean;
  north_star: string | null;
  north_star_context: string | null;
  workspace_stamped: boolean;
  coverage: InterviewCoverage;
  findings: DiscoveryFinding[];
  low_hanging_fruit: LowHangingFruitCandidate[];
  status: string;
  internal_only: boolean;
  requires_human_review: boolean;
};

/** An evidence-backed finding. This is the governed side: it carries review and eligibility. */
export type AssessmentFinding = {
  finding_id: string;
  evidence_id: string;
  statement: string | null;
  statement_available: boolean;
  source_reference_ids: string[];
  review_status: string;
  stored_review_status: string | null;
  supporting_review_ids: string[];
  reliability: string | null;
  claim_scope: string | null;
  recommendation_eligible: boolean;
  recommendation_blocked_reasons: string[];
  recommendation_id: string | null;
};

export type InternalRecommendation = {
  recommendation_id: string;
  finding_id: string;
  text: string;
  supporting_evidence_ids: string[];
  supporting_source_ids: string[];
  supporting_review_ids: string[];
  internal_only: boolean;
  requires_human_review: boolean;
};

export type InternalAssessment = {
  engagement_id: string | null;
  client_id: string | null;
  owner_id: string | null;
  authorization_scope: string | null;
  audience: string;
  status: string;
  client_facing: boolean;
  requires_human_review: boolean;
  findings: AssessmentFinding[];
  confidence_notes: string[];
  excluded_evidence: { evidence_id: string; reason: string }[];
  limitations: string[];
  recommendation_status: string;
  recommendation_blocked_reasons: string[];
  recommendations: InternalRecommendation[];
  /** Null when the engagement has no discovery material. */
  discovery: DiscoveryAssessmentContext | null;
};

export type AssessmentResponse = {
  engagement: Engagement;
  assessment: InternalAssessment;
  markdown: string;
};

// --- Phase 208: final report foundation (internal, derived, read-only) -------------------------

export type ReportSectionKey =
  | "executive_overview"
  | "discovery_summary"
  | "low_hanging_fruit"
  | "evidence_findings"
  | "recommendations"
  | "limitations";

/** Consecutive candidates sharing the consultant's entered value and effort. Not a tier or rank. */
export type LowHangingFruitGroup = {
  estimated_value: Level | null;
  estimated_effort: Level | null;
  label: string;
  candidates: LowHangingFruitCandidate[];
};

export type FinalReport = {
  kind: string;
  status: string;
  audience: string;
  client_facing: boolean;
  approved_for_client: boolean;
  requires_human_review: boolean;
  section_order: ReportSectionKey[];
  section_titles: Record<ReportSectionKey, string>;
  executive_overview: {
    engagement_id: string | null;
    engagement_label: string | null;
    client_id: string | null;
    client_name: string | null;
    north_star: string | null;
    north_star_context: string | null;
    summary: string[];
  };
  discovery_summary: {
    material: string;
    available: boolean;
    coverage: InterviewCoverage | null;
    findings: DiscoveryFinding[];
    limitations: string[];
  };
  low_hanging_fruit: {
    material: string;
    grouping_note: string;
    not_ranked_note: string;
    groups: LowHangingFruitGroup[];
  };
  evidence_findings: {
    material: string;
    findings: AssessmentFinding[];
    confidence_notes: string[];
    excluded_evidence: { evidence_id: string; reason: string }[];
  };
  recommendations: {
    material: string;
    status: string;
    recommendations: InternalRecommendation[];
    blocked_reasons: string[];
  };
  limitations: {
    boundary_statements: string[];
    assessment_limitations: string[];
    discovery_limitations: string[];
  };
};

export type FinalReportResponse = {
  engagement: Engagement;
  report: FinalReport;
  markdown: string;
};

// --- Phase 213: release packages, two-stage approval and release (internal only) -------------

export type PackageState =
  | "prepared" | "lead_approved" | "final_approved" | "released" | "superseded" | "rejected";

export type PersonRef = { id: string; name: string | null };

export type ApprovalDecision = {
  id: string;
  decision: "approved" | "rejected";
  by: PersonRef;
  at: string | null;
  note: string | null;
  package_hash: string;
  content_hash: string;
  /** The client-facing rendition this person reviewed; the decision covers the whole package. */
  reviewed_rendition: "web" | "docx";
  designation_id: string | null;
};

export type Designation = {
  id: string;
  number: number;
  consultant: PersonRef;
  by: PersonRef;
  at: string | null;
  supersedes_designation_id: string | null;
};

export type Rendition = {
  id: string;
  media_type: string;
  file_name: string | null;
  rendered_by: string;
  byte_length: number;
  rendition_hash: string;
};

/**
 * One release package: an immutable report version bound to its stored web and DOCX renditions,
 * and its approval chain. Internal: never part of client-facing output.
 */
export type ReleasePackage = {
  id: string;
  artifact_id: string;
  engagement_id: string;
  package_number: number;
  artifact_version_id: string;
  version_number: number | null;
  content_hash: string;
  package_hash: string;
  hash_verified: boolean;
  /** Why the stored renditions are not client-facing; empty when the package can be approved. */
  client_problems: string[];
  renditions: { web?: Rendition; docx?: Rendition };
  created_by: PersonRef | null;
  created_at: string | null;
  supersedes_package_id: string | null;
  superseded_by_package_id: string | null;
  state: PackageState;
  lead_decision: ApprovalDecision | null;
  final_decision: ApprovalDecision | null;
  current_designation: { id: string; consultant: PersonRef; by: PersonRef; at: string | null } | null;
  designations: Designation[];
  release: { id: string; by: PersonRef; at: string | null; package_hash: string } | null;
  source: SourceMarker | null;
};

export type FinalReportReview = {
  engagement_id: string;
  artifact_id: string | null;
  packages: ReleasePackage[];
  draft_content_hash: string | null;
  draft_matches_latest: boolean;
};

/** The stored web rendition's exact HTML, for review. Never re-rendered. */
export async function getWebRendition(packageId: string): Promise<string> {
  const res = await apiFetch(`/release-packages/${encodeURIComponent(packageId)}/web`);
  if (res.status === 401) redirect("/login");
  if (!res.ok) throw new Error(`Peak API web rendition failed (${res.status})`);
  return res.text();
}

// --- Phase 217/218: engagement phases and guided work plans ------------------------------------

export type PhaseStatus = "planned" | "authorized" | "completed";
export type TaskStatus = "suggested" | "open" | "in_progress" | "completed" | "not_applicable";
/** The record kinds a consultant can enter today. Photo and document capture is reserved. */
export type WorkRecordKind = "note" | "interview_response" | "measurement" | "mismatch";
export type RecordKind = WorkRecordKind | "photo" | "document_photo" | "document";

export type PhaseAuthorization = {
  basis: string | null;
  reference: string | null;
  authorized_by: string | null;
  authorized_at: string | null;
};

export type EngagementPhaseSummary = {
  id: string;
  engagement_id: string;
  title: string;
  scope_summary: string;
  status: PhaseStatus;
  origin: "roadmap_item" | "manual";
  roadmap_item_id: string | null;
  origin_note: string | null;
  authorized: boolean;
  authorization: PhaseAuthorization | null;
  work_plan_status: "not_started" | "draft" | "active" | "closed";
  completed_at: string | null;
  created_at: string | null;
};

/** What a consultant recorded while doing a task. Insert-only; a correction supersedes. */
export type TaskRecord = {
  id: string;
  task_id: string;
  record_kind: RecordKind;
  record_text: string;
  structured: Record<string, string | number>;
  basis: ObservationBasis | null;
  supersedes_record_id: string | null;
  superseded_by: string | null;
  recorded_by: string | null;
  created_at: string | null;
};

export type TaskRef = { task_id: string; sequence: number; title: string };

/** Decided by the API's rules; the UI shows it and never re-derives it. */
export type TaskWorkState = {
  /** Conditional task: true/false once its condition task is resolved, null while pending. */
  applies: boolean | null;
  prerequisites: (TaskRef & { resolved: boolean })[];
  condition_task: TaskRef | null;
  record_missing: boolean;
  completion_blockers: { code: string; message: string }[];
};

export type PhaseTask = {
  id: string;
  phase_id: string;
  sequence: number;
  title: string;
  instructions: string;
  why_it_matters: string | null;
  what_to_observe: string | null;
  suggested_evidence: RecordKind[];
  follow_up_questions: string[];
  expected_result: string | null;
  required: boolean;
  requires_record: boolean;
  condition: { task_id: string; record_kind: RecordKind } | null;
  origin: "peak_method" | "consultant" | "si_suggested";
  /** Template step key ("template.step") for a Peak Method task; null otherwise. */
  template_key: string | null;
  inclusion_reason: string | null;
  added_after_authorization: boolean;
  status: TaskStatus;
  result_summary: string | null;
  not_applicable_reason: string | null;
  completed_by: string | null;
  completed_at: string | null;
  records: TaskRecord[];
  work_state: TaskWorkState;
};

export type ReadinessItem = {
  code: string;
  reason_text: string | null;
  task_id?: string;
  sequence?: number;
  title?: string;
};

export type PhaseReadiness = {
  ready: boolean;
  phase_status: PhaseStatus;
  required_tasks: number;
  required_resolved: number;
  blocking: ReadinessItem[];
  notes: ReadinessItem[];
  rule: string;
};

export type EngagementPhaseDetail = EngagementPhaseSummary & {
  roadmap_item: { id: string; title: string; status: string } | null;
  tasks: PhaseTask[];
  readiness: PhaseReadiness;
};

// --- Phase 219: roadmap and phase setup ----------------------------------------------------------

export type RoadmapStatus = "proposed" | "accepted" | "deferred" | "declined" | "superseded";
export type RoadmapDecision = "proposed" | "accepted" | "deferred" | "declined";

/** Proposed future work, stored on the engagement's roadmap. Advisory: never authorized work. */
export type RoadmapItem = {
  id: string;
  sequence: number;
  title: string;
  problem_framing: string;
  rationale: string;
  expected_outcome: string;
  source_observation_ids: string[];
  origin: "peak_method" | "consultant" | "si_suggested";
  template_key: string | null;
  status: RoadmapStatus;
  status_note: string | null;
  supersedes_item_id: string | null;
  decided_at: string | null;
  created_at: string | null;
  /** Decided by the API's rules: the statuses a decision may set now. */
  decisions: RoadmapDecision[];
  revisable: boolean;
  /** The phase created from this item, if any. */
  phase_id: string | null;
  decided_by: string | null;
};

/** Computed by Peak from discovery observations each time; nothing is stored until it is added. */
export type RoadmapSuggestion = {
  template_key: string;
  title: string;
  problem_framing: string;
  rationale: string;
  expected_outcome: string;
  source_observation_ids: string[];
  grounding: string;
};

export type Roadmap = {
  engagement_id: string;
  /** False for engagements created outside the consultant workspace (no roadmap work there). */
  enabled: boolean;
  items: RoadmapItem[];
  superseded: RoadmapItem[];
  suggestions: RoadmapSuggestion[];
};

/** A Peak Method phase template: the starting work plan for a phase. */
export type PhaseTemplate = {
  template_key: string;
  title: string;
  problem_framing: string;
  expected_outcome: string;
  scope_summary: string;
  tasks: { sequence: number; title: string; required: boolean }[];
};

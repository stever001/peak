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
  engagement_count: number;
};

export type Engagement = {
  id: string;
  engagement_label: string | null;
  objective: string | null;
  status: string | null;
  current_phase: string | null;
  client: { id: string; name: string | null };
  assigned_consultant: { id: string; name: string | null } | null;
};

export type Client = {
  id: string;
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
};

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
  session: { id: string; interviewee_name: string } | null;
  recorded_by: string | null;
  created_at: string | null;
};

export type Discovery = {
  engagement_id: string;
  discovery_enabled: boolean;
  north_star: string | null;
  north_star_context: string | null;
  key_personnel: KeyPerson[];
  sessions: SessionSummary[];
  observations: Observation[];
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

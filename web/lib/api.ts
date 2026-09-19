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

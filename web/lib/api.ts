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

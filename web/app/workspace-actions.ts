"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";
import type { FormState } from "@/app/actions";

const CLIENT_FIELDS = [
  "organization_label", "description", "address_line1", "address_line2", "city", "region",
  "postal_code", "country", "contact_name", "contact_title", "contact_email", "contact_phone",
] as const;

const ENGAGEMENT_FIELDS = [
  "engagement_label", "objective", "assigned_consultant_id", "status", "current_phase",
] as const;

/** The listed fields the form actually submitted. An absent field (e.g. a disabled control) is left
 *  out rather than sent as empty, so it is never cleared by accident. */
function pick(formData: FormData, fields: readonly string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields) if (formData.has(field)) out[field] = String(formData.get(field) ?? "");
  return out;
}

function clientBody(formData: FormData) {
  let keyPersonnel: unknown = [];
  try {
    keyPersonnel = JSON.parse(String(formData.get("key_personnel") ?? "[]"));
  } catch {
    keyPersonnel = [];
  }
  return { ...pick(formData, CLIENT_FIELDS), key_personnel: keyPersonnel };
}

/** Phase 215: present only when the internal test option was chosen. The server forces the
 *  classification; an engagement also passes the confirmation, which the server requires. */
function internalTest(formData: FormData) {
  if (formData.get("internal_test") !== "true") return {};
  return formData.get("internal_test_confirmed") === "true"
    ? { internal_test: true, internal_test_confirmed: true } : { internal_test: true };
}

/** Turn an API refusal into a short message for the form. */
async function refusal(res: Response): Promise<FormState> {
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return { error: "That record no longer exists." };
  const detail = (await res.json().catch(() => null))?.detail;
  if (typeof detail?.message === "string") return { error: detail.message };
  return { error: "Check the highlighted details and try again." };
}

async function send(path: string, method: "POST" | "PATCH", body: unknown) {
  return apiFetch(path, { method, body: JSON.stringify(body) });
}

export async function createClient(_prev: FormState, formData: FormData): Promise<FormState> {
  const test = formData.get("internal_test") === "true";
  const res = await send("/clients", "POST", { ...clientBody(formData), ...(test ? { internal_test: true } : {}) });
  if (!res.ok) return refusal(res);
  const { client } = await res.json();
  revalidatePath("/clients");
  // Opened from the engagement form's "Create internal test client": go back to it, with this client chosen.
  if (test && formData.get("return_to") === "engagement") {
    redirect(`/engagements/new?type=internal_test&client=${encodeURIComponent(client.id)}`);
  }
  redirect(`/clients/${client.id}`);
}

export async function updateClient(
  id: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/clients/${encodeURIComponent(id)}`, "PATCH", clientBody(formData));
  if (!res.ok) return refusal(res);
  revalidatePath(`/clients/${id}`);
  redirect(`/clients/${id}`);
}

export async function createEngagement(_prev: FormState, formData: FormData): Promise<FormState> {
  const body = { ...pick(formData, ENGAGEMENT_FIELDS), client_id: String(formData.get("client_id") ?? ""),
                 ...internalTest(formData) };
  const res = await send("/engagements", "POST", body);
  if (!res.ok) return refusal(res);
  const { engagement } = await res.json();
  revalidatePath("/engagements");
  redirect(`/engagements/${engagement.id}`);
}

/** Phase 215: an Admin's logical deletion of an internal test engagement; the name must be retyped. */
export async function deleteInternalTestEngagement(
  id: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/engagements/${encodeURIComponent(id)}/internal-test-deletion`, "POST",
                         { confirm_engagement_label: String(formData.get("confirm_engagement_label") ?? "") });
  if (!res.ok) return refusal(res);
  revalidatePath("/engagements");
  redirect("/engagements");
}

export async function updateEngagement(
  id: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/engagements/${encodeURIComponent(id)}`, "PATCH",
                         pick(formData, ENGAGEMENT_FIELDS));
  if (!res.ok) return refusal(res);
  revalidatePath(`/engagements/${id}`);
  redirect(`/engagements/${id}`);
}

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

function pick(formData: FormData, fields: readonly string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields) out[field] = String(formData.get(field) ?? "");
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
  const res = await send("/clients", "POST", clientBody(formData));
  if (!res.ok) return refusal(res);
  const { client } = await res.json();
  revalidatePath("/clients");
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
  const body = { ...pick(formData, ENGAGEMENT_FIELDS), client_id: String(formData.get("client_id") ?? "") };
  const res = await send("/engagements", "POST", body);
  if (!res.ok) return refusal(res);
  const { engagement } = await res.json();
  revalidatePath("/engagements");
  redirect(`/engagements/${engagement.id}`);
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

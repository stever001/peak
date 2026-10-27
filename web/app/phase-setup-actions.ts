"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, type Roadmap } from "@/lib/api";
import type { FormState } from "@/app/actions";
import { roadmapItemPayload } from "@/lib/phase-setup";

/**
 * Phase 219: roadmap and phase-setup actions. Each calls one existing Phase 217 endpoint; the API
 * decides every rule (transitions, who may record authorization, duplicate templates) and its
 * refusals are shown as given.
 */

async function send(path: string, body?: unknown) {
  return apiFetch(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

async function refusal(res: Response): Promise<FormState> {
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return { error: "That roadmap item or phase no longer exists." };
  const detail = (await res.json().catch(() => null))?.detail;
  if (typeof detail?.message === "string") return { error: detail.message };
  return { error: "Check the details and try again." };
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "").trim();
const fields = (formData: FormData) =>
  Object.fromEntries([...formData.entries()].map(([k, v]) => [k, String(v)]));
const roadmapPath = (engagementId: string) => `/engagements/${engagementId}/roadmap`;

function refreshEngagement(engagementId: string) {
  revalidatePath(roadmapPath(engagementId));
  revalidatePath(`/engagements/${engagementId}`);
}

// --- Roadmap -------------------------------------------------------------------------------------

/**
 * Add a Peak suggestion to the roadmap. The suggestion is looked up again on the server, so the
 * observations it cites are exactly the ones Peak computed; the browser sends only its template.
 */
export async function addSuggestionToRoadmap(engagementId: string, templateKey: string): Promise<FormState> {
  const res = await apiFetch(`/engagements/${encodeURIComponent(engagementId)}/roadmap`);
  if (!res.ok) return refusal(res);
  const { roadmap } = (await res.json()) as { roadmap: Roadmap };
  const s = roadmap.suggestions.find((x) => x.template_key === templateKey);
  if (!s) return { error: "Peak no longer suggests this, or it is already on the roadmap." };
  const created = await send(`/engagements/${encodeURIComponent(engagementId)}/roadmap-items`,
                             { template_key: s.template_key, source_observation_ids: s.source_observation_ids });
  if (!created.ok) return refusal(created);
  refreshEngagement(engagementId);
  return { success: "Added to the roadmap as proposed work." };
}

export async function createRoadmapItem(
  engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const observations = formData.getAll("source_observation_ids").map(String).filter(Boolean);
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/roadmap-items`,
                         roadmapItemPayload(fields(formData), observations));
  if (!res.ok) return refusal(res);
  refreshEngagement(engagementId);
  return { success: "Added to the roadmap as proposed work." };
}

export async function decideRoadmapItem(
  engagementId: string, itemId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const note = text(formData, "note");
  const res = await send(`/roadmap-items/${encodeURIComponent(itemId)}/decision`,
                         { status: text(formData, "status"), ...(note ? { note } : {}) });
  if (!res.ok) return refusal(res);
  refreshEngagement(engagementId);
  return { success: "Decision recorded." };
}

export async function reviseRoadmapItem(
  engagementId: string, itemId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/roadmap-items/${encodeURIComponent(itemId)}/revision`,
                         roadmapItemPayload(fields(formData)));
  if (!res.ok) return refusal(res);
  refreshEngagement(engagementId);
  return { success: "Revision saved; the earlier version is kept." };
}

// --- Phases --------------------------------------------------------------------------------------

/** Create a planned phase from an accepted roadmap item, then open its setup. */
export async function createPhaseFromRoadmapItem(
  engagementId: string, itemId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const title = text(formData, "title");
  const scope = text(formData, "scope_summary");
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/phases`, {
    roadmap_item_id: itemId, ...(title ? { title } : {}), ...(scope ? { scope_summary: scope } : {}),
  });
  if (!res.ok) return refusal(res);
  const { phase } = await res.json();
  refreshEngagement(engagementId);
  redirect(`/phases/${phase.id}/setup`);
}

/** Create a planned phase with no roadmap item; the API requires the reason it exists. */
export async function createManualPhase(
  engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/phases`, {
    title: text(formData, "title"), scope_summary: text(formData, "scope_summary"),
    origin_note: text(formData, "origin_note"),
  });
  if (!res.ok) return refusal(res);
  const { phase } = await res.json();
  refreshEngagement(engagementId);
  redirect(`/phases/${phase.id}/setup`);
}

function refreshPhase(phaseId: string, engagementId: string) {
  revalidatePath(`/phases/${phaseId}/setup`);
  revalidatePath(`/phases/${phaseId}`);
  refreshEngagement(engagementId);
}

/** Record that the client authorized this phase. The API allows only the Lead or an Admin. */
export async function recordPhaseAuthorization(
  phaseId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  if (formData.get("confirm") !== "yes") {
    return { error: "Confirm that the client has authorized this phase of work." };
  }
  const reference = text(formData, "authorization_reference");
  const res = await send(`/phases/${encodeURIComponent(phaseId)}/authorization`, {
    authorization_basis: text(formData, "authorization_basis"),
    ...(reference ? { authorization_reference: reference } : {}),
  });
  if (!res.ok) return refusal(res);
  refreshPhase(phaseId, engagementId);
  return { success: "Authorization recorded." };
}

/** Load a Peak Method template's tasks into the phase's work plan. */
export async function loadTemplateTasks(
  phaseId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const templateKey = text(formData, "template_key");
  if (!templateKey) return { error: "Choose a work plan template." };
  const res = await send(`/phases/${encodeURIComponent(phaseId)}/template-tasks`, { template_key: templateKey });
  if (!res.ok) return refusal(res);
  refreshPhase(phaseId, engagementId);
  return { success: "Work plan tasks loaded." };
}

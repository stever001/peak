"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";
import type { FormState } from "@/app/actions";
import { recordPayload } from "@/lib/work-plan";

/** Phase 218: guided work-plan actions. The API decides every rule; refusals are shown as given. */

async function send(path: string, body?: unknown) {
  return apiFetch(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

async function refusal(res: Response): Promise<FormState> {
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return { error: "That task or phase no longer exists." };
  const detail = (await res.json().catch(() => null))?.detail;
  if (typeof detail?.message === "string") return { error: detail.message };
  return { error: "Check the details and try again." };
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "");
const taskPath = (phaseId: string, taskId: string) => `/phases/${phaseId}/tasks/${taskId}`;

function refresh(phaseId: string, taskId?: string) {
  revalidatePath(`/phases/${phaseId}`);
  if (taskId) revalidatePath(taskPath(phaseId, taskId));
}

export async function recordTaskWork(
  phaseId: string, taskId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const fields = Object.fromEntries([...formData.entries()].map(([k, v]) => [k, String(v)]));
  const body = recordPayload(fields);
  const res = await send(`/tasks/${encodeURIComponent(taskId)}/records`, body);
  if (!res.ok) return refusal(res);
  refresh(phaseId, taskId);
  if (body.supersedes_record_id) redirect(`${taskPath(phaseId, taskId)}#records`);
  return { success: "Saved to this task's records." };
}

export async function completeTask(
  phaseId: string, taskId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/tasks/${encodeURIComponent(taskId)}/completion`,
                         { result_summary: text(formData, "result_summary") });
  if (!res.ok) return refusal(res);
  refresh(phaseId, taskId);
  return { success: "Task completed." };
}

export async function resolveTaskNotApplicable(
  phaseId: string, taskId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/tasks/${encodeURIComponent(taskId)}/not-applicable`,
                         { reason: text(formData, "reason") });
  if (!res.ok) return refusal(res);
  refresh(phaseId, taskId);
  return { success: "Marked not applicable." };
}

export async function acceptSuggestedTask(phaseId: string, taskId: string): Promise<FormState> {
  const res = await send(`/tasks/${encodeURIComponent(taskId)}/acceptance`);
  if (!res.ok) return refusal(res);
  refresh(phaseId, taskId);
  return { success: "Added to the work plan." };
}

export async function completePhase(phaseId: string): Promise<FormState> {
  const res = await send(`/phases/${encodeURIComponent(phaseId)}/completion`);
  if (!res.ok) return refusal(res);
  refresh(phaseId);
  return { success: "Phase work marked complete." };
}

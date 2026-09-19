"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch, type InterviewSession } from "@/lib/api";
import type { FormState } from "@/app/actions";

async function send(path: string, method: "POST" | "PATCH" | "PUT", body?: unknown) {
  return apiFetch(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
}

async function refusal(res: Response): Promise<FormState> {
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return { error: "That record no longer exists." };
  const detail = (await res.json().catch(() => null))?.detail;
  if (typeof detail?.message === "string") return { error: detail.message };
  return { error: "Check the details and try again." };
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "");
const level = (formData: FormData, name: string) => text(formData, name) || null;

// --- North Star --------------------------------------------------------------------------------

export async function saveNorthStar(
  engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/north-star`, "PATCH", {
    north_star: text(formData, "north_star"),
    north_star_context: text(formData, "north_star_context"),
  });
  if (!res.ok) return refusal(res);
  revalidatePath(`/engagements/${engagementId}`);
  return { success: "North Star saved." };
}

// --- Interviews --------------------------------------------------------------------------------

export async function startInterview(
  engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/sessions`, "POST", {
    interviewee_name: text(formData, "interviewee_name"),
    interviewee_title: text(formData, "interviewee_title"),
    notes: text(formData, "notes"),
  });
  if (!res.ok) return refusal(res);
  const { session } = await res.json();
  redirect(`/interviews/${session.id}`);
}

/** Save one answer, then move to the next / previous shown question or stay. */
export async function saveAnswer(
  sessionId: string, questionId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(
    `/sessions/${encodeURIComponent(sessionId)}/answers/${encodeURIComponent(questionId)}`, "PUT",
    { answer: text(formData, "answer") },
  );
  if (!res.ok) return refusal(res);
  const { session } = (await res.json()) as { session: InterviewSession };
  const ids = session.questions.map((q) => q.id);
  const at = ids.indexOf(questionId);
  const intent = text(formData, "intent");
  const target = intent === "prev" ? ids[at - 1] : intent === "next" ? ids[at + 1] : questionId;
  revalidatePath(`/interviews/${sessionId}`);
  redirect(target ? `/interviews/${sessionId}?q=${target}` : `/interviews/${sessionId}?review=1`);
}

export async function completeInterview(sessionId: string): Promise<void> {
  const res = await send(`/sessions/${encodeURIComponent(sessionId)}/complete`, "POST");
  if (res.status === 401) redirect("/login");
  revalidatePath(`/interviews/${sessionId}`);
  redirect(`/interviews/${sessionId}`);
}

// --- Observations ------------------------------------------------------------------------------

function observationBody(formData: FormData) {
  return {
    category: text(formData, "category"),
    observation_text: text(formData, "observation_text"),
    low_hanging_fruit: formData.get("low_hanging_fruit") === "on",
    estimated_effort: level(formData, "estimated_effort"),
    estimated_value: level(formData, "estimated_value"),
  };
}

export async function createObservation(
  engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const sessionId = text(formData, "session_id");
  const res = await send(`/engagements/${encodeURIComponent(engagementId)}/observations`, "POST", {
    ...observationBody(formData), ...(sessionId ? { session_id: sessionId } : {}),
  });
  if (!res.ok) return refusal(res);
  revalidatePath(`/engagements/${engagementId}`);
  return { success: "Observation recorded." };
}

export async function updateObservation(
  observationId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/observations/${encodeURIComponent(observationId)}`, "PATCH",
                         observationBody(formData));
  if (!res.ok) return refusal(res);
  revalidatePath(`/engagements/${engagementId}`);
  redirect(`/engagements/${engagementId}#discovery`);
}

// --- Question pool -----------------------------------------------------------------------------

function questionBody(formData: FormData, editing: boolean) {
  const answerType = text(formData, "answer_type");
  const choices = text(formData, "choices").split("\n").map((c) => c.trim()).filter(Boolean);
  const branchQuestion = text(formData, "branch_question_id");
  const order = text(formData, "display_order").trim();
  return {
    prompt: text(formData, "prompt"),
    category: text(formData, "category"),
    answer_type: answerType,
    choices: answerType === "single_choice" ? choices : null,
    ...(order ? { display_order: Number(order) } : {}),
    ...(editing ? { active: formData.get("active") === "on" } : {}),
    branch: branchQuestion
      ? { question_id: branchQuestion, operator: text(formData, "branch_operator"),
          value: text(formData, "branch_value") }
      : null,
  };
}

export async function createQuestion(_prev: FormState, formData: FormData): Promise<FormState> {
  const res = await send("/questions", "POST", questionBody(formData, false));
  if (!res.ok) return refusal(res);
  revalidatePath("/questions");
  redirect("/questions");
}

export async function updateQuestion(
  questionId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  const res = await send(`/questions/${encodeURIComponent(questionId)}`, "PATCH",
                         questionBody(formData, true));
  if (!res.ok) return refusal(res);
  revalidatePath("/questions");
  redirect("/questions");
}

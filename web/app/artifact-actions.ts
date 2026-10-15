"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { apiFetch } from "@/lib/api";
import type { FormState } from "@/app/actions";

/**
 * Phase 213 internal review actions. Each posts one explicit act on one release package; the API
 * checks the actor, the order, the distinct-human rule and the package hash, and its refusal is shown.
 */
async function post(path: string, body?: unknown): Promise<Response> {
  return apiFetch(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

async function refusal(res: Response): Promise<FormState> {
  if (res.status === 401) redirect("/login");
  if (res.status === 404) return { error: "That record no longer exists." };
  const detail = (await res.json().catch(() => null))?.detail;
  if (typeof detail?.message === "string") return { error: detail.message };
  return { error: "That action was refused. Reload and try again." };
}

const text = (formData: FormData, name: string) => String(formData.get(name) ?? "");
const packagePath = (packageId: string, act: string) =>
  `/release-packages/${encodeURIComponent(packageId)}/${act}`;

async function done(res: Response, engagementId: string, success: string): Promise<FormState> {
  if (!res.ok) return refusal(res);
  revalidatePath(`/engagements/${engagementId}/final-report`);
  return { success };
}

export async function prepareReleasePackage(engagementId: string): Promise<FormState> {
  const res = await post(`/engagements/${encodeURIComponent(engagementId)}/final-report/packages`);
  if (!res.ok) return refusal(res);
  const { package: pkg } = await res.json();
  revalidatePath(`/engagements/${engagementId}/final-report`);
  return { success: pkg.created ? "Release package prepared for review." : "Nothing changed; the latest package already holds this report." };
}

function decisionBody(formData: FormData) {
  return {
    decision: text(formData, "decision"),
    package_hash: text(formData, "package_hash"),
    reviewed_rendition: text(formData, "reviewed_rendition"),
    note: text(formData, "note"),
  };
}

export async function leadDecision(
  packageId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  return done(await post(packagePath(packageId, "lead-approval"), decisionBody(formData)),
              engagementId, "Lead Consultant decision recorded.");
}

export async function designateFinalApprover(
  packageId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  return done(await post(packagePath(packageId, "final-approver"),
                         { consultant_id: text(formData, "consultant_id") }),
              engagementId, "Final Approver designated.");
}

export async function finalDecision(
  packageId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  return done(await post(packagePath(packageId, "final-approval"), decisionBody(formData)),
              engagementId, "Final Approver decision recorded.");
}

export async function releasePackage(
  packageId: string, engagementId: string, _prev: FormState, formData: FormData,
): Promise<FormState> {
  return done(await post(packagePath(packageId, "release"),
                         { package_hash: text(formData, "package_hash") }),
              engagementId, "Package released.");
}

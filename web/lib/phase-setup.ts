import type {
  EngagementPhaseSummary, PhaseTask, RoadmapDecision, RoadmapItem, RoadmapStatus,
} from "@/lib/api";

/**
 * Phase 219: display helpers for preparing an engagement phase. Pure functions, no rules: what a
 * roadmap item allows next comes from the API (`decisions`), and every setup step is read from
 * records that already exist (the phase's status and its work plan). Nothing here is stored.
 */

export const ROADMAP_STATUS_LABELS: Record<RoadmapStatus, string> = {
  proposed: "Proposed",
  accepted: "Accepted",
  deferred: "Deferred",
  declined: "Declined",
  superseded: "Replaced by a revision",
};

/** Button labels for the decisions the API offers on a roadmap item. */
export const DECISION_LABELS: Record<RoadmapDecision, string> = {
  accepted: "Accept",
  deferred: "Defer",
  declined: "Decline",
  proposed: "Return to proposed",
};

export const ROADMAP_ORIGIN_LABELS: Record<RoadmapItem["origin"], string> = {
  peak_method: "Peak Method suggestion added to the roadmap",
  consultant: "Added by a consultant",
  si_suggested: "Synthesis suggestion added to the roadmap",
};

/** Where a phase stands in setup, read from its status and whether its work plan has tasks. */
export type SetupStage = "plan_and_authorization" | "authorization" | "plan" | "ready" | "completed";

type PhaseState = Pick<EngagementPhaseSummary, "status" | "work_plan_status">;

export function setupStage(p: PhaseState): SetupStage {
  if (p.status === "completed") return "completed";
  const hasPlan = p.work_plan_status !== "not_started";
  if (p.status === "authorized") return hasPlan ? "ready" : "plan";
  return hasPlan ? "authorization" : "plan_and_authorization";
}

export const SETUP_STAGE_LABELS: Record<SetupStage, string> = {
  plan_and_authorization: "Setup: load the work plan and record authorization",
  authorization: "Setup: awaiting client authorization",
  plan: "Setup: load the initial work plan",
  ready: "Ready for guided execution",
  completed: "Phase work completed",
};

/** Setup is finished once the phase is authorized and has a work plan (or is completed). */
export function setupFinished(p: PhaseState): boolean {
  const stage = setupStage(p);
  return stage === "ready" || stage === "completed";
}

/** The page to open for a phase: its setup until setup is finished, then its work plan. */
export function phaseHref(p: PhaseState & { id: string }): string {
  return setupFinished(p) ? `/phases/${p.id}` : `/phases/${p.id}/setup`;
}

export type SetupStep = { key: string; label: string; done: boolean };

/** The fixed setup steps for a phase that exists, each done or not from its records. */
export function setupSteps(p: PhaseState & Pick<EngagementPhaseSummary, "origin" | "authorized">): SetupStep[] {
  const hasPlan = p.work_plan_status !== "not_started";
  return [
    { key: "source", done: true,
      label: p.origin === "roadmap_item" ? "Proposed work accepted on the roadmap"
        : "Reason for a manually created phase recorded" },
    { key: "phase", label: "Engagement phase created", done: true },
    { key: "plan", label: "Initial work plan loaded", done: hasPlan },
    { key: "authorization", label: "Client authorization recorded", done: p.authorized },
    { key: "ready", label: "Ready for guided execution", done: p.authorized && hasPlan },
  ];
}

/** Template keys whose tasks are already in the plan (a task's key is "template.step"). */
export function templatesInPlan(tasks: Pick<PhaseTask, "template_key">[]): Set<string> {
  return new Set(tasks.map((t) => t.template_key?.split(".")[0]).filter((k): k is string => !!k));
}

/** The text fields of a roadmap item form, trimmed; blank fields are left out. */
export function roadmapItemPayload(fields: Record<string, string>, observationIds: string[] = []) {
  const out: Record<string, string | string[]> = {};
  for (const name of ["title", "problem_framing", "rationale", "expected_outcome"]) {
    const v = (fields[name] ?? "").trim();
    if (v) out[name] = v;
  }
  if (observationIds.length) out.source_observation_ids = observationIds;
  return out;
}

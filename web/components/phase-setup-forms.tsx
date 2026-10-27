"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { Observation, PhaseTemplate, RoadmapDecision, RoadmapItem } from "@/lib/api";
import { DECISION_LABELS } from "@/lib/phase-setup";

type FormAction = (prev: FormState, formData: FormData) => Promise<FormState>;

const SECONDARY = "inline-flex min-h-touch items-center justify-center rounded-peak border border-ink bg-surface px-6 font-medium";

/** Roadmap item framing: add new proposed work, or revise a proposed / deferred item. */
export function RoadmapItemForm({ action, item, observations = [], submitLabel }: {
  action: FormAction;
  /** Revising: the item whose wording is the starting point. */
  item?: RoadmapItem;
  /** Discovery observations the new item may rest on (optional for a consultant item). */
  observations?: Observation[];
  submitLabel: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const id = (name: string) => `${item?.id ?? "new"}-${name}`;
  return (
    <form key={item ? undefined : state.success} action={formAction} className="space-y-4">
      <Field label="Title" htmlFor={id("title")} hint="A short name for the proposed work.">
        <input id={id("title")} name="title" required maxLength={255} defaultValue={item?.title ?? ""}
               className="peak-input" />
      </Field>
      <Field label="Operational issue or improvement opportunity" htmlFor={id("problem_framing")}>
        <textarea id={id("problem_framing")} name="problem_framing" rows={3} required maxLength={4000}
                  defaultValue={item?.problem_framing ?? ""} className="peak-input min-h-24 py-3" />
      </Field>
      <Field label="Why it matters" htmlFor={id("rationale")}>
        <textarea id={id("rationale")} name="rationale" rows={3} required maxLength={4000}
                  defaultValue={item?.rationale ?? ""} className="peak-input min-h-24 py-3" />
      </Field>
      <Field label="Expected outcome" htmlFor={id("expected_outcome")}>
        <textarea id={id("expected_outcome")} name="expected_outcome" rows={3} required maxLength={4000}
                  defaultValue={item?.expected_outcome ?? ""} className="peak-input min-h-24 py-3" />
      </Field>
      {!item && observations.length > 0 && (
        <fieldset>
          <legend className="peak-label">Discovery observations this rests on (optional)</legend>
          <ul className="space-y-2">
            {observations.map((o) => (
              <li key={o.id}>
                <label className="flex min-h-touch cursor-pointer items-start gap-3 rounded-peak border border-line px-4 py-3">
                  <input type="checkbox" name="source_observation_ids" value={o.id} className="mt-1 size-5 shrink-0" />
                  <span className="min-w-0 break-words">{o.observation_text}</span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
      )}
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}

/** The decisions the API allows on this item now, with an optional note. */
export function RoadmapDecisionForm({ action, decisions, itemId }: {
  action: FormAction; decisions: RoadmapDecision[]; itemId: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-3">
      <Field label="Note on this decision (optional)" htmlFor={`${itemId}-note`}
             hint="For example, what the client said and when.">
        <input id={`${itemId}-note`} name="note" maxLength={4000} className="peak-input" />
      </Field>
      <FormMessage state={state} />
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        {decisions.map((d) => (
          <button key={d} type="submit" name="status" value={d} disabled={pending}
                  className={d === "accepted" ? "peak-button" : SECONDARY}>
            {DECISION_LABELS[d]}
          </button>
        ))}
      </div>
    </form>
  );
}

/** Create the planned phase for an accepted roadmap item. Blank fields take the item's wording. */
export function CreatePhaseForm({ action, itemId, defaultTitle, defaultScope }: {
  action: FormAction; itemId: string; defaultTitle: string; defaultScope: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-4">
      <Field label="Phase title" htmlFor={`${itemId}-phase-title`} hint="Leave as is to use the roadmap item's title.">
        <input id={`${itemId}-phase-title`} name="title" maxLength={255} defaultValue={defaultTitle}
               className="peak-input" />
      </Field>
      <Field label="Phase objective and scope" htmlFor={`${itemId}-phase-scope`}
             hint="What this phase of consultant work covers. Starts from the suggested scope; adjust it to what the client is being asked to authorize.">
        <textarea id={`${itemId}-phase-scope`} name="scope_summary" rows={4} maxLength={4000}
                  defaultValue={defaultScope} className="peak-input min-h-28 py-3" />
      </Field>
      <p className="text-sm text-ink-muted">
        The phase starts as planned. Nothing can be recorded against it until the client&apos;s authorization is recorded.
      </p>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? "Creating…" : "Create engagement phase"}
      </button>
    </form>
  );
}

/** A phase created without a roadmap item: title, scope and the required reason. */
export function ManualPhaseForm({ action }: { action: FormAction }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-4">
      <Field label="Phase title" htmlFor="manual-title">
        <input id="manual-title" name="title" required maxLength={255} className="peak-input" />
      </Field>
      <Field label="Phase objective and scope" htmlFor="manual-scope">
        <textarea id="manual-scope" name="scope_summary" rows={4} required maxLength={4000}
                  className="peak-input min-h-28 py-3" />
      </Field>
      <Field label="Why this phase is being created without a roadmap item" htmlFor="manual-reason"
             hint="Required. Kept with the phase so others can see it was created manually.">
        <textarea id="manual-reason" name="origin_note" rows={3} required maxLength={4000}
                  className="peak-input min-h-24 py-3" />
      </Field>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className={`${SECONDARY} w-full sm:w-auto`}>
        {pending ? "Creating…" : "Create phase manually"}
      </button>
    </form>
  );
}

/** Record the client's authorization of this phase. An operational record only. */
export function AuthorizationForm({ action }: { action: FormAction }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  return (
    <form action={formAction} className="space-y-4">
      <Field label="What the client authorized, who authorized it, and how" htmlFor="authorization_basis"
             hint="For example: Operations Manager approved the receiving phase as scoped, by email on 24 October.">
        <textarea id="authorization_basis" name="authorization_basis" rows={4} required maxLength={4000}
                  className="peak-input min-h-28 py-3" />
      </Field>
      <Field label="Reference (optional)" htmlFor="authorization_reference"
             hint="Where the authorization can be found, such as an email subject or meeting date.">
        <input id="authorization_reference" name="authorization_reference" maxLength={255} className="peak-input" />
      </Field>
      <label className="flex min-h-touch cursor-pointer items-start gap-3 rounded-peak border border-line px-4 py-3">
        <input type="checkbox" name="confirm" value="yes" required className="mt-1 size-5 shrink-0" />
        <span>The client has authorized this phase of work.</span>
      </label>
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? "Recording…" : "Record authorization"}
      </button>
    </form>
  );
}

/** Choose a Peak Method template and load its tasks into the work plan. */
export function TemplateForm({ action, templates, recommended, loaded, afterAuthorization }: {
  action: FormAction;
  templates: PhaseTemplate[];
  /** The roadmap item's template, chosen by default. */
  recommended: string | null;
  /** Templates whose tasks are already in this plan. */
  loaded: string[];
  /** The phase is already authorized, so loaded tasks are marked as added after authorization. */
  afterAuthorization: boolean;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const initial = recommended && !loaded.includes(recommended) ? recommended : undefined;
  return (
    <form action={formAction} className="space-y-4">
      <fieldset className="space-y-3">
        <legend className="peak-label">Work plan template</legend>
        {templates.map((t) => (
          <label key={t.template_key}
                 className="flex cursor-pointer items-start gap-3 rounded-peak border border-line bg-surface px-4 py-4 has-[:checked]:border-2 has-[:checked]:border-brand">
            <input type="radio" name="template_key" value={t.template_key} required
                   defaultChecked={t.template_key === initial} className="mt-1 size-5 shrink-0" />
            <span className="min-w-0 flex-1 space-y-2">
              <span className="flex flex-wrap items-start justify-between gap-2">
                <span className="font-semibold text-brand">{t.title}</span>
                <span className="flex flex-wrap gap-2 text-xs font-semibold">
                  {t.template_key === recommended && <span className="rounded-full bg-accent px-3 py-1">Matches the roadmap item</span>}
                  {loaded.includes(t.template_key) && <span className="rounded-full bg-line px-3 py-1">Already in this work plan</span>}
                </span>
              </span>
              <span className="block text-sm">{t.scope_summary}</span>
              <span className="block text-sm text-ink-muted">
                {t.tasks.length} tasks: {t.tasks.map((s) => `${s.sequence}. ${s.title}${s.required ? "" : " (optional)"}`).join(" · ")}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      {afterAuthorization && (
        <p className="text-sm text-ink-muted">
          This phase is already authorized, so these tasks will be marked as added after authorization.
        </p>
      )}
      <FormMessage state={state} />
      <button type="submit" disabled={pending} className="peak-button w-full sm:w-auto">
        {pending ? "Loading…" : "Load work plan tasks"}
      </button>
    </form>
  );
}

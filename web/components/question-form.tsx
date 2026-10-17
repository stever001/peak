"use client";

import Link from "next/link";
import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Field } from "@/components/field";
import { FormMessage } from "@/components/form-message";
import type { Question } from "@/lib/api";
import { ANSWER_TYPE_LABELS, FINDING_CLASS_LABELS } from "@/lib/labels";

type Action = (prev: FormState, formData: FormData) => Promise<FormState>;

export function QuestionForm({ action, question, allQuestions, categories, submitLabel, engagement, returnTo }: {
  action: Action;
  question?: Question;
  allQuestions: Question[];
  categories: string[];
  submitLabel: string;
  /** Phase 216: adding a supplemental question within this engagement (asked only there). */
  engagement?: { id: string; name: string | null };
  returnTo?: string;
}) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(action, {});
  const [answerType, setAnswerType] = useState(question?.answer_type ?? "short_text");
  const [parentId, setParentId] = useState(question?.branch?.question_id ?? "");
  const parent = allQuestions.find((q) => q.id === parentId);
  const parentValues = parent?.answer_type === "yes_no" ? ["yes", "no"]
    : parent?.answer_type === "single_choice" ? parent.choices : [];
  // Only earlier questions asked in the same interviews can be branched on; the server re-checks.
  const scope = question ? question.engagement_id : engagement?.id ?? null;
  const candidates = allQuestions.filter((q) => q.id !== question?.id
    && (!question || q.display_order < question.display_order)
    && (q.engagement_id === null || q.engagement_id === scope));
  const supplemental = !question?.canonical;
  const rationaleRequired = scope !== null;

  return (
    <form action={formAction} className="peak-card space-y-5">
      {engagement && <input type="hidden" name="engagement_id" value={engagement.id} />}
      {returnTo && <input type="hidden" name="return_to" value={returnTo} />}
      {engagement && (
        <p className="rounded-peak border border-line bg-canvas p-3 text-sm">
          Supplemental question for {engagement.name ?? "this engagement"}: it is asked only in this engagement&rsquo;s
          interviews. It does not become a Peak Method question; an Admin may review it for the canonical pool later.
        </p>
      )}
      <Field label="Question" htmlFor="prompt">
        <textarea id="prompt" name="prompt" rows={3} required maxLength={1000}
                  defaultValue={question?.prompt ?? ""} className="peak-input min-h-24 py-3" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Category" htmlFor="category">
          <input id="category" name="category" required maxLength={64} list="question-categories"
                 defaultValue={question?.category ?? ""} className="peak-input" />
          <datalist id="question-categories">
            {categories.map((c) => <option key={c} value={c} />)}
          </datalist>
        </Field>
        <Field label="Answer type" htmlFor="answer_type">
          <select id="answer_type" name="answer_type" value={answerType}
                  onChange={(e) => setAnswerType(e.target.value as Question["answer_type"])}
                  className="peak-input">
            {Object.entries(ANSWER_TYPE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        {answerType === "single_choice" && (
          <Field label="Choices (one per line)" htmlFor="choices" wide>
            <textarea id="choices" name="choices" rows={4} defaultValue={question?.choices.join("\n") ?? ""}
                      className="peak-input min-h-28 py-3" />
          </Field>
        )}
        <Field label="Display order" htmlFor="display_order"
               hint={question ? "Lower numbers come first." : "Leave blank to add at the end."}>
          <input id="display_order" name="display_order" type="number" min={0} inputMode="numeric"
                 defaultValue={question?.display_order ?? ""} className="peak-input" />
        </Field>
        {question && (
          <label className="flex min-h-touch items-center gap-3 self-end rounded-peak border border-line bg-surface px-4">
            <input type="checkbox" name="active" defaultChecked={question.active} className="size-5 accent-brand" />
            <span className="font-medium">Active (shown in new interviews)</span>
          </label>
        )}
      </div>

      <fieldset className="rounded-peak border border-line p-4">
        <legend className="px-1 text-sm font-semibold">Show only when… (optional)</legend>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Earlier question" htmlFor="branch_question_id">
            <select id="branch_question_id" name="branch_question_id" value={parentId}
                    onChange={(e) => setParentId(e.target.value)} className="peak-input">
              <option value="">Always show</option>
              {candidates.map((q) => (
                <option key={q.id} value={q.id}>{q.prompt.length > 60 ? `${q.prompt.slice(0, 60)}…` : q.prompt}</option>
              ))}
            </select>
          </Field>
          <Field label="Is" htmlFor="branch_operator">
            <select id="branch_operator" name="branch_operator" disabled={!parentId}
                    defaultValue={question?.branch?.operator ?? "equals"} className="peak-input">
              <option value="equals">equal to</option>
              <option value="not_equals">not equal to</option>
            </select>
          </Field>
          <Field label="Value" htmlFor="branch_value">
            {parentValues.length ? (
              <select id="branch_value" name="branch_value" disabled={!parentId}
                      defaultValue={question?.branch?.value ?? parentValues[0]} className="peak-input">
                {parentValues.map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            ) : (
              <input id="branch_value" name="branch_value" disabled={!parentId} maxLength={255}
                     defaultValue={question?.branch?.value ?? ""} className="peak-input" />
            )}
          </Field>
        </div>
      </fieldset>

      {supplemental && (
        <fieldset className="rounded-peak border border-line p-4">
          <legend className="px-1 text-sm font-semibold">Why ask it</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={rationaleRequired ? "Rationale" : "Rationale (optional)"} htmlFor="rationale" wide
                   hint="What you expect it to expose or rule out. Kept with the question for later review.">
              <textarea id="rationale" name="rationale" rows={3} maxLength={4000} required={rationaleRequired}
                        defaultValue={question?.rationale ?? ""} className="peak-input min-h-24 py-3" />
            </Field>
            <Field label="Domain (optional)" htmlFor="domain" wide>
              <input id="domain" name="domain" maxLength={128} defaultValue={question?.domain ?? ""}
                     className="peak-input" />
            </Field>
          </div>
          <p className="mt-4 mb-2 text-sm font-medium">Finding classes (optional)</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(FINDING_CLASS_LABELS).map(([code, label]) => (
              <label key={code} className="flex min-h-10 items-center gap-3 text-sm">
                <input type="checkbox" name="finding_classes" value={code}
                       defaultChecked={question?.finding_classes.includes(code)} className="size-5 accent-brand" />
                <span><span className="font-semibold">{code}</span> — {label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      <FormMessage state={state} />
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Link href={returnTo ?? "/questions"}
              className="inline-flex min-h-touch items-center justify-center rounded-peak border border-line px-6 font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={pending} className="peak-button">
          {pending ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

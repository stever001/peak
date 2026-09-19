import Link from "next/link";

import { completeInterview, saveAnswer } from "@/app/discovery-actions";
import { AnswerStepForm } from "@/components/answer-step-form";
import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type InterviewSession } from "@/lib/api";
import { formatDate } from "@/lib/labels";

function display(answer: string | null) {
  if (!answer) return <span className="text-ink-muted">Not answered</span>;
  return <span className="whitespace-pre-line">{answer === "yes" ? "Yes" : answer === "no" ? "No" : answer}</span>;
}

export default async function InterviewPage(props: PageProps<"/interviews/[id]">) {
  await requireConsultant();
  const { id } = await props.params;
  const search = await props.searchParams;
  const { session: s } = await apiGet<{ session: InterviewSession }>(`/sessions/${encodeURIComponent(id)}`);
  const answered = s.questions.filter((q) => q.answer).length;
  const open = s.status === "in_progress";
  const reviewing = !open || search.review === "1";
  const requested = typeof search.q === "string" ? search.q : null;
  const index = Math.max(0, requested ? s.questions.findIndex((q) => q.id === requested)
    : s.questions.findIndex((q) => !q.answer));
  const step = s.questions[index];

  return (
    <>
      <Link href={`/engagements/${s.engagement.id}#discovery`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← {s.engagement.name ?? "Engagement"}
      </Link>
      <PageHeader title={`Interview: ${s.interviewee_name}`}
                  intro={[s.interviewee_title, s.client.name, s.conducted_by && `with ${s.conducted_by}`,
                          formatDate(s.started_at)].filter(Boolean).join(" · ")} />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex-1">
          <p className="mb-2 text-sm text-ink-muted">
            {answered} of {s.questions.length} shown questions answered
            {open ? "" : " · completed"}
          </p>
          <div className="h-2 overflow-hidden rounded-full bg-line" aria-hidden="true">
            <div className="h-full bg-brand" style={{ width: `${s.questions.length ? (answered / s.questions.length) * 100 : 0}%` }} />
          </div>
        </div>
        {open && (
          <div className="flex gap-3">
            {!reviewing && (
              <Link href={`/interviews/${s.id}?review=1`}
                    className="inline-flex min-h-touch items-center rounded-peak border border-line bg-surface px-4 font-medium">
                Review all
              </Link>
            )}
            <form action={completeInterview.bind(null, s.id)}>
              <button type="submit" className="min-h-touch rounded-peak border border-brand bg-surface px-4 font-medium text-brand">
                Complete interview
              </button>
            </form>
          </div>
        )}
      </div>

      {!reviewing && step ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
          <section className="peak-card">
            <p className="mb-1 text-sm font-medium text-ink-muted">
              {step.category} · Question {index + 1} of {s.questions.length}
            </p>
            <h2 className="mb-5 text-xl font-semibold md:text-2xl">{step.prompt}</h2>
            <AnswerStepForm action={saveAnswer.bind(null, s.id, step.id)} step={step} hasPrev={index > 0} />
          </section>
          <nav aria-label="Questions" className="peak-card hidden max-h-[70vh] overflow-y-auto lg:block">
            <ol className="space-y-1">
              {s.questions.map((q, i) => (
                <li key={q.id}>
                  <Link href={`/interviews/${s.id}?q=${q.id}`} aria-current={i === index ? "step" : undefined}
                        className={`flex min-h-10 items-start gap-2 rounded-peak px-2 py-2 text-sm ${i === index ? "bg-canvas font-semibold" : "hover:bg-canvas"}`}>
                    <span aria-hidden="true" className={q.answer ? "text-brand" : "text-ink-muted"}>{q.answer ? "✓" : "○"}</span>
                    <span>{q.prompt}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </nav>
        </div>
      ) : (
        <section className="peak-card">
          <h2 className="mb-4 text-lg font-semibold">{open ? "All questions" : "Answers"}</h2>
          <ol className="divide-y divide-line">
            {s.questions.map((q) => (
              <li key={q.id} className="py-4">
                <p className="text-sm text-ink-muted">{q.category}</p>
                <p className="font-medium">{q.prompt}</p>
                <p className="mt-1">{display(q.answer)}</p>
                {open && (
                  <Link href={`/interviews/${s.id}?q=${q.id}`} className="inline-flex min-h-touch items-center text-sm font-medium text-brand">
                    {q.answer ? "Change answer" : "Answer"}
                  </Link>
                )}
              </li>
            ))}
          </ol>
          {s.history.length > 0 && (
            <>
              <h3 className="mt-6 mb-2 font-semibold">Earlier answers no longer in the question flow</h3>
              <ul className="divide-y divide-line">
                {s.history.map((h) => (
                  <li key={h.question_id} className="py-3">
                    <p className="font-medium">{h.prompt}</p>
                    <p className="mt-1">{display(h.answer)}</p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </>
  );
}

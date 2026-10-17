import Link from "next/link";

import { createQuestion } from "@/app/discovery-actions";
import { PageHeader } from "@/components/page-header";
import { QuestionForm } from "@/components/question-form";
import { apiGet, requireConsultant, type Question } from "@/lib/api";

/**
 * Add a question. Opened from an engagement (`?engagement=`), it is a supplemental question recorded
 * with that engagement, its author and a rationale, and asked only there. Without an engagement it is a
 * global question, which only an Admin may add (Phase 216). Canonical Peak Method questions come only
 * from the instrument; this form never creates one.
 */
export default async function NewQuestionPage(props: PageProps<"/questions/new">) {
  const me = await requireConsultant();
  const params = await props.searchParams;
  const engagementId = typeof params.engagement === "string" && params.engagement ? params.engagement : null;
  if (!engagementId && me.role !== "admin") {
    // A global question is asked in every engagement, so only an Admin adds one (Phase 216).
    return (
      <>
        <PageHeader title="Add question" />
        <div className="peak-card space-y-3">
          <p>Questions asked in every engagement are maintained by an Admin.</p>
          <p className="text-ink-muted">
            To ask something more in one engagement, open that engagement and choose &ldquo;Add supplemental
            question&rdquo; in its Discovery section or in an interview.
          </p>
          <Link href="/engagements" className="inline-flex min-h-touch items-center font-medium text-brand">Engagements</Link>
        </div>
      </>
    );
  }
  const returnTo = typeof params.return_to === "string" && params.return_to.startsWith("/")
    && !params.return_to.startsWith("//") ? params.return_to : undefined;
  const [{ questions }, engagement] = await Promise.all([
    apiGet<{ questions: Question[] }>(engagementId
      ? `/questions?engagement_id=${encodeURIComponent(engagementId)}` : "/questions"),
    engagementId
      ? apiGet<{ engagement: { id: string; engagement_label: string | null } }>(
        `/engagements/${encodeURIComponent(engagementId)}`).then((r) => r.engagement)
      : Promise.resolve(null),
  ]);
  return (
    <>
      <PageHeader title={engagement ? "Add supplemental question" : "Add question"} />
      <QuestionForm action={createQuestion} allQuestions={questions}
                    categories={[...new Set(questions.map((q) => q.category))]} submitLabel="Add question"
                    engagement={engagement ? { id: engagement.id, name: engagement.engagement_label } : undefined}
                    returnTo={returnTo} />
    </>
  );
}

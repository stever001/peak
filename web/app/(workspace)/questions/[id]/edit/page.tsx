import Link from "next/link";

import { updateQuestion } from "@/app/discovery-actions";
import { PageHeader } from "@/components/page-header";
import { QuestionForm } from "@/components/question-form";
import { apiGet, requireConsultant, type Question } from "@/lib/api";
import { ANSWER_TYPE_LABELS } from "@/lib/labels";

/** Edit a question. A Peak Method (canonical) question is read-only unless you are an Admin (Phase 216). */
export default async function EditQuestionPage(props: PageProps<"/questions/[id]/edit">) {
  const me = await requireConsultant();
  const { id } = await props.params;
  const [{ question }, { questions }] = await Promise.all([
    apiGet<{ question: Question }>(`/questions/${encodeURIComponent(id)}`),
    apiGet<{ questions: Question[] }>("/questions"),
  ]);
  if (question.admin_controlled && me.role !== "admin") {
    return (
      <>
        <PageHeader title={question.canonical ? "Peak Method question" : "Global question"} />
        <div className="peak-card space-y-3">
          <p className="text-sm text-ink-muted">{question.category} · {ANSWER_TYPE_LABELS[question.answer_type]}
            {question.active ? "" : " · Inactive"}</p>
          <p className="text-lg font-medium">{question.prompt}</p>
          <p className="text-ink-muted">
            Peak Method and other global questions are maintained by an Admin. To ask something more in one
            engagement, add a supplemental question from that engagement&rsquo;s Discovery section.
          </p>
          <Link href="/questions" className="inline-flex min-h-touch items-center font-medium text-brand">← Question pool</Link>
        </div>
      </>
    );
  }
  return (
    <>
      <PageHeader title={question.canonical ? "Edit Peak Method question" : "Edit question"} />
      <QuestionForm action={updateQuestion.bind(null, question.id)} question={question} allQuestions={questions}
                    categories={[...new Set(questions.map((q) => q.category))]} submitLabel="Save changes" />
    </>
  );
}

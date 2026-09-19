import { updateQuestion } from "@/app/discovery-actions";
import { PageHeader } from "@/components/page-header";
import { QuestionForm } from "@/components/question-form";
import { apiGet, requireConsultant, type Question } from "@/lib/api";

export default async function EditQuestionPage(props: PageProps<"/questions/[id]/edit">) {
  await requireConsultant();
  const { id } = await props.params;
  const [{ question }, { questions }] = await Promise.all([
    apiGet<{ question: Question }>(`/questions/${encodeURIComponent(id)}`),
    apiGet<{ questions: Question[] }>("/questions"),
  ]);
  return (
    <>
      <PageHeader title="Edit question" />
      <QuestionForm action={updateQuestion.bind(null, question.id)} question={question} allQuestions={questions}
                    categories={[...new Set(questions.map((q) => q.category))]} submitLabel="Save changes" />
    </>
  );
}

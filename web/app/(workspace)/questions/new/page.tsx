import { createQuestion } from "@/app/discovery-actions";
import { PageHeader } from "@/components/page-header";
import { QuestionForm } from "@/components/question-form";
import { apiGet, requireConsultant, type Question } from "@/lib/api";

export default async function NewQuestionPage() {
  await requireConsultant();
  const { questions } = await apiGet<{ questions: Question[] }>("/questions");
  return (
    <>
      <PageHeader title="Add question" />
      <QuestionForm action={createQuestion} allQuestions={questions}
                    categories={[...new Set(questions.map((q) => q.category))]} submitLabel="Add question" />
    </>
  );
}

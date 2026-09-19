import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { apiGet, requireConsultant, type Question } from "@/lib/api";
import { ANSWER_TYPE_LABELS } from "@/lib/labels";

export default async function QuestionsPage() {
  await requireConsultant();
  const { questions } = await apiGet<{ questions: Question[] }>("/questions");
  const byId = new Map(questions.map((q) => [q.id, q]));
  const categories = [...new Set(questions.map((q) => q.category))];
  return (
    <>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Question pool"
                    intro="Interview questions, in the order they are asked. Deactivate a question instead of deleting it; past answers are kept." />
        <Link href="/questions/new" className="peak-button shrink-0">Add question</Link>
      </div>
      {questions.length === 0 && (
        <div className="peak-card text-ink-muted">The question pool is empty. Add the first question.</div>
      )}
      <div className="space-y-6">
        {categories.map((category) => (
          <section key={category} className="peak-card">
            <h2 className="mb-3 text-lg font-semibold">{category}</h2>
            <ul className="divide-y divide-line">
              {questions.filter((q) => q.category === category).map((q) => {
                const parent = q.branch ? byId.get(q.branch.question_id) : undefined;
                return (
                  <li key={q.id}>
                    <Link href={`/questions/${q.id}/edit`}
                          className={`flex min-h-touch flex-col gap-1 py-3 hover:text-brand ${q.active ? "" : "opacity-60"}`}>
                      <span className="font-medium">{q.prompt}</span>
                      <span className="text-sm text-ink-muted">
                        {[ANSWER_TYPE_LABELS[q.answer_type], q.active ? null : "Inactive",
                          parent ? `Shown when "${parent.prompt}" ${q.branch!.operator === "equals" ? "is" : "is not"} ${q.branch!.value}` : null,
                        ].filter(Boolean).join(" · ")}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </>
  );
}

import Link from "next/link";

import { loadTemplateTasks, recordPhaseAuthorization } from "@/app/phase-setup-actions";
import { PageHeader } from "@/components/page-header";
import { AuthorizationForm, TemplateForm } from "@/components/phase-setup-forms";
import { SetupChecklist } from "@/components/phase-setup-parts";
import { PhaseStatusPill } from "@/components/work-plan-parts";
import {
  apiGet, requireConsultant, type Engagement, type EngagementPhaseDetail, type PhaseTemplate, type Roadmap,
} from "@/lib/api";
import { formatDate } from "@/lib/labels";
import { setupStage, setupSteps, templatesInPlan } from "@/lib/phase-setup";

const SUMMARY = "inline-flex min-h-touch cursor-pointer items-center font-medium text-brand";

/** Phase 219: prepare one engagement phase, then hand off to its guided work plan (Phase 218). */
export default async function PhaseSetupPage(props: PageProps<"/phases/[id]/setup">) {
  const me = await requireConsultant();
  const { id } = await props.params;
  const { phase: p } = await apiGet<{ phase: EngagementPhaseDetail }>(`/phases/${encodeURIComponent(id)}`);
  const eid = encodeURIComponent(p.engagement_id);
  const [{ engagement: e }, { roadmap }, { templates }] = await Promise.all([
    apiGet<{ engagement: Engagement }>(`/engagements/${eid}`),
    apiGet<{ roadmap: Roadmap }>(`/engagements/${eid}/roadmap`),
    apiGet<{ templates: PhaseTemplate[] }>("/phase-templates"),
  ]);
  const item = p.roadmap_item_id ? roadmap.items.find((i) => i.id === p.roadmap_item_id) : undefined;
  const plan = p.tasks.filter((t) => t.status !== "suggested");
  const stage = setupStage(p);
  const loaded = [...templatesInPlan(p.tasks)];
  const a = p.authorization;
  // Display only: the API decides who may record authorization (the engagement's Lead or an Admin).
  const mayAuthorize = me.role === "admin" || e.assigned_consultant?.id === me.id;
  const templateForm = (
    <TemplateForm action={loadTemplateTasks.bind(null, p.id, p.engagement_id)} templates={templates}
                  recommended={item?.template_key ?? null} loaded={loaded} afterAuthorization={p.status === "authorized"} />
  );

  return (
    <>
      <Link href={`/engagements/${p.engagement_id}/roadmap`}
            className="mb-4 inline-flex min-h-touch items-center text-sm font-medium text-brand">
        ← Roadmap and phase setup
      </Link>
      <div className="mb-2"><PhaseStatusPill status={p.status} /></div>
      <PageHeader title={p.title} intro="Phase setup" />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-start">
        <div className="min-w-0 space-y-6">
          {(stage === "ready" || stage === "completed") && (
            <Link href={`/phases/${p.id}`}
                  className="flex min-h-touch items-center justify-between gap-3 rounded-peak bg-brand px-5 py-4 text-on-brand hover:bg-brand-strong">
              <span>
                <span className="block text-sm opacity-80">
                  {stage === "ready" ? "Setup is finished" : "Phase work completed"}
                </span>
                <span className="font-semibold">{stage === "ready" ? "Open work plan" : "View work plan"}</span>
              </span>
              <span aria-hidden="true">→</span>
            </Link>
          )}

          <section className="peak-card">
            <dl className="space-y-4">
              <div>
                <dt className="text-sm text-ink-muted">Phase objective and scope</dt>
                <dd className="mt-0.5 whitespace-pre-line break-words">{p.scope_summary}</dd>
              </div>
              {item && (
                <>
                  <div>
                    <dt className="text-sm text-ink-muted">Operational issue or opportunity</dt>
                    <dd className="mt-0.5 whitespace-pre-line break-words">{item.problem_framing}</dd>
                  </div>
                  <div>
                    <dt className="text-sm text-ink-muted">Expected outcome</dt>
                    <dd className="mt-0.5 whitespace-pre-line break-words">{item.expected_outcome}</dd>
                  </div>
                </>
              )}
              <div>
                <dt className="text-sm text-ink-muted">Source</dt>
                <dd className="mt-0.5 break-words">
                  {p.origin === "manual"
                    ? <>Created manually. Reason: <span className="whitespace-pre-line">{p.origin_note}</span></>
                    : <>Roadmap item: {p.roadmap_item?.title}</>}
                </dd>
              </div>
            </dl>
          </section>

          <section aria-labelledby="plan-step" className="peak-card space-y-4">
            <h2 id="plan-step" className="text-lg font-semibold">Initial work plan</h2>
            {plan.length > 0 ? (
              <>
                <p>{plan.length} {plan.length === 1 ? "task is" : "tasks are"} in the work plan:</p>
                <ol className="space-y-1 text-sm">
                  {plan.map((t) => (
                    <li key={t.id} className="break-words">
                      {t.sequence}. {t.title}{t.required ? "" : " (optional)"}
                      {t.added_after_authorization && <span className="text-ink-muted"> · added after authorization</span>}
                    </li>
                  ))}
                </ol>
                {p.status === "planned" && (
                  <Link href={`/phases/${p.id}`} className="inline-flex min-h-touch items-center font-medium text-brand">
                    Preview the work plan (read-only until authorized) →
                  </Link>
                )}
                {p.status !== "completed" && (
                  <details className="rounded-peak border border-line p-4">
                    <summary className={SUMMARY}>Add another template&apos;s tasks</summary>
                    <div className="mt-3">{templateForm}</div>
                  </details>
                )}
              </>
            ) : (
              <>
                <p className="text-ink-muted">
                  Choose the Peak Method template that fits this phase. Its ordered tasks become the work plan.
                  {p.status === "planned" && " Load it before recording authorization, so the client authorizes the plan you will follow."}
                </p>
                {templateForm}
              </>
            )}
          </section>

          <section aria-labelledby="authorization-step" className="peak-card space-y-4">
            <h2 id="authorization-step" className="text-lg font-semibold">Client authorization</h2>
            {a ? (
              <div>
                <p className="whitespace-pre-line break-words">{a.basis}</p>
                <p className="mt-1 text-sm text-ink-muted">
                  {[a.reference && `Reference: ${a.reference}`, a.authorized_by && `Recorded by ${a.authorized_by}`,
                    formatDate(a.authorized_at)].filter(Boolean).join(" · ")}
                </p>
              </div>
            ) : (
              <>
                <p>
                  This records that the client has authorized this phase of work. It is an operational record: it does
                  not record a proposal, a signed contract or a payment. Until it is recorded, the phase stays planned
                  and no work can be recorded against it.
                </p>
                {mayAuthorize ? (
                  <AuthorizationForm action={recordPhaseAuthorization.bind(null, p.id, p.engagement_id)} />
                ) : (
                  <p role="status" className="rounded-peak border-l-4 border-l-highlight bg-canvas px-4 py-3">
                    Only the engagement&apos;s Lead ({e.assigned_consultant?.name ?? "not assigned"}) or an Admin can
                    record authorization.
                  </p>
                )}
              </>
            )}
          </section>
        </div>

        <aside className="peak-card order-first space-y-3 xl:order-none xl:sticky xl:top-6">
          <h2 className="text-lg font-semibold">Setup progress</h2>
          <SetupChecklist steps={setupSteps(p)} />
        </aside>
      </div>
    </>
  );
}

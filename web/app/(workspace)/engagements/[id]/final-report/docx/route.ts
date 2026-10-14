import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { apiFetch } from "@/lib/api";

/**
 * Download the engagement's Final Report as DOCX. A server-side pass-through: the Python API renders
 * the document from the same composed report the page shows, and the session cookie never leaves the
 * server. Read-only — GET is the only method, and nothing is written or stored.
 */
export async function GET(_request: NextRequest, ctx: RouteContext<"/engagements/[id]/final-report/docx">) {
  const { id } = await ctx.params;
  const res = await apiFetch(`/engagements/${encodeURIComponent(id)}/final-report.docx`);
  if (res.status === 401) redirect("/login");
  if (!res.ok) return new Response(res.status === 404 ? "Not found" : "Export failed", { status: res.status });
  return new Response(res.body, {
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/octet-stream",
      "content-disposition": res.headers.get("content-disposition") ?? 'attachment; filename="final-report.docx"',
      "cache-control": "no-store",
    },
  });
}

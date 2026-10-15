import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { apiFetch } from "@/lib/api";

/**
 * Download a release package's stored DOCX: the exact file prepared with the package (Phase 213), never a
 * regeneration. A server-side pass-through; the session cookie never leaves the server. GET only.
 */
export async function GET(_request: NextRequest, ctx: RouteContext<"/release-packages/[id]/docx">) {
  const { id } = await ctx.params;
  const res = await apiFetch(`/release-packages/${encodeURIComponent(id)}/docx`);
  if (res.status === 401) redirect("/login");
  if (!res.ok) return new Response(res.status === 404 ? "Not found" : "Unavailable", { status: res.status });
  return new Response(res.body, {
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/octet-stream",
      "content-disposition": res.headers.get("content-disposition") ?? 'attachment; filename="report.docx"',
      "cache-control": "no-store",
    },
  });
}

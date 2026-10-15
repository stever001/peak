import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { apiFetch } from "@/lib/api";

/**
 * A release package's stored web page: the exact HTML prepared with the package (Phase 213), never a fresh
 * rendering. Served as a static document: no script may run and nothing external is fetched. GET only.
 */
export async function GET(_request: NextRequest, ctx: RouteContext<"/release-packages/[id]/web">) {
  const { id } = await ctx.params;
  const res = await apiFetch(`/release-packages/${encodeURIComponent(id)}/web`);
  if (res.status === 401) redirect("/login");
  if (!res.ok) return new Response(res.status === 404 ? "Not found" : "Unavailable", { status: res.status });
  return new Response(res.body, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'",
      "cache-control": "no-store",
    },
  });
}

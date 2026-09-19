import { NextResponse, type NextRequest } from "next/server";

/**
 * Optimistic check only: send visitors without a session cookie to /login.
 * Real authentication and the Admin check happen in the Python API on every request.
 */
export function proxy(request: NextRequest) {
  if (!request.cookies.has("peak_session")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/dashboard/:path*", "/clients/:path*", "/engagements/:path*", "/consultants/:path*",
            "/interviews/:path*", "/observations/:path*", "/questions/:path*"],
};

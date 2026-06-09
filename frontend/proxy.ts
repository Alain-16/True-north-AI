import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Next 16 renamed `middleware` → `proxy` (Node runtime). Per Next's auth guide,
// this does an OPTIMISTIC cookie-presence check only — real session validation
// happens server-side (auth() in components, getToken() in the BFF). Cheap redirect,
// not a security boundary on its own.

// Auth.js v5 session cookie names (http dev vs https prod).
const SESSION_COOKIES = ["authjs.session-token", "__Secure-authjs.session-token"];

export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = SESSION_COOKIES.some((c) => req.cookies.has(c));
  const isLogin = pathname === "/login";

  // Unauthenticated → only /login is reachable.
  if (!hasSession && !isLogin) {
    return NextResponse.redirect(new URL("/login", req.nextUrl));
  }
  // Already signed in → keep them out of /login.
  if (hasSession && isLogin) {
    return NextResponse.redirect(new URL("/chat", req.nextUrl));
  }
  return NextResponse.next();
}

export const config = {
  // Guard page routes only. Exclude /api (route handlers self-enforce via getToken),
  // Next internals, and static assets.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};

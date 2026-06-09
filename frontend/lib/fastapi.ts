import "server-only";
import { getToken } from "next-auth/jwt";

// Server-only fetch wrapper for the FastAPI backend. Used by the BFF route
// handlers and the Auth.js callbacks — never from the browser.
const BASE = process.env.FASTAPI_INTERNAL_URL ?? "http://localhost:8000";

export function fastapi(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

// Decode a JWT payload without verifying (we just received it over a trusted
// server-side call). Node runtime → Buffer is available.
export function decodeJwtPayload<T = Record<string, unknown>>(token: string): T {
  const payload = token.split(".")[1];
  return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as T;
}

// Call FastAPI on behalf of the signed-in patient. Reads the raw session JWT
// (which holds the access token) server-side and forwards it as a Bearer token.
// The browser never sees the access token. Returns 401 if there's no session.
export async function fastapiAuthed(
  req: Request,
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const secure = process.env.NODE_ENV === "production";
  const cookieName = secure
    ? "__Secure-authjs.session-token"
    : "authjs.session-token";

  const token = await getToken({
    req,
    secret: process.env.AUTH_SECRET!,
    salt: cookieName,
    secureCookie: secure,
    cookieName,
  });

  const accessToken = (token as { accessToken?: string } | null)?.accessToken;
  if (!accessToken) {
    return new Response(JSON.stringify({ error: "unauthenticated" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

import { NextResponse } from "next/server";
import { fastapi } from "@/lib/fastapi";

// BFF for login step 1. Forwards { phone, email } to FastAPI /auth/request-otp.
// Always returns the same generic body (anti-enumeration mirrors the backend) —
// the browser can't tell whether the account exists or the email failed.
const GENERIC = { message: "If those details match an account, a code has been sent." };

export async function POST(req: Request) {
  try {
    const { phone, email } = await req.json();
    await fastapi("/auth/request-otp", {
      method: "POST",
      body: JSON.stringify({ phone, email }),
    });
  } catch {
    // Swallow — stay opaque to the client regardless of backend/transport errors.
  }
  return NextResponse.json(GENERIC);
}

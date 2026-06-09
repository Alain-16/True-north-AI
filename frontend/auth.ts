import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import type { JWT } from "next-auth/jwt";
import { fastapi, decodeJwtPayload } from "@/lib/fastapi";

type AccessClaims = { sub: string; openmrs_patient_id?: string; exp: number };

// Refresh the access token via FastAPI /auth/refresh (which rotates the refresh
// token too). On failure we tag the token with an error so the app can force re-login.
async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    if (!token.refreshToken) throw new Error("missing refresh token");
    const res = await fastapi("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: token.refreshToken }),
    });
    if (!res.ok) throw new Error(`refresh failed: ${res.status}`);
    const { access_token, refresh_token } = await res.json();
    const claims = decodeJwtPayload<AccessClaims>(access_token);
    return {
      ...token,
      accessToken: access_token,
      refreshToken: refresh_token, // rotation — store the new one
      accessTokenExpires: claims.exp * 1000,
      error: undefined,
    };
  } catch {
    return { ...token, error: "RefreshTokenError" };
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [
    Credentials({
      credentials: { phone: {}, code: {} },
      authorize: async (credentials) => {
        const phone = credentials?.phone as string | undefined;
        const code = credentials?.code as string | undefined;
        if (!phone || !code) return null;

        const res = await fastapi("/auth/verify-otp", {
          method: "POST",
          body: JSON.stringify({ phone, code }),
        });
        if (!res.ok) return null; // 401 → failed sign-in

        const { access_token, refresh_token } = await res.json();
        const claims = decodeJwtPayload<AccessClaims>(access_token);
        return {
          id: String(claims.sub),
          openmrsPatientId: claims.openmrs_patient_id ?? "",
          accessToken: access_token,
          refreshToken: refresh_token,
          accessTokenExpires: claims.exp * 1000,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // Initial sign-in: copy tokens off the authorized user onto the JWT.
      if (user) {
        token.patientId = user.id;
        token.openmrsPatientId = user.openmrsPatientId;
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.accessTokenExpires = user.accessTokenExpires;
        return token;
      }
      // Still valid (60s skew buffer) → use as-is.
      if (token.accessTokenExpires && Date.now() < token.accessTokenExpires - 60_000) {
        return token;
      }
      // Expired → silently refresh.
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      // Expose ONLY identity + error to the client. Raw tokens stay in the JWT
      // (read server-side via getToken in the BFF) and never reach the browser.
      session.patientId = token.patientId;
      session.openmrsPatientId = token.openmrsPatientId;
      session.error = token.error;
      return session;
    },
  },
});

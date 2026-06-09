import type { DefaultSession } from "next-auth";

// Custom fields carried through authorize() -> jwt() -> session().
// Raw access/refresh tokens live in the JWT (server-side cookie) only — they are
// deliberately NOT surfaced on Session (the browser never sees them).

declare module "next-auth" {
  interface User {
    openmrsPatientId?: string;
    accessToken?: string;
    refreshToken?: string;
    accessTokenExpires?: number; // epoch ms
  }

  interface Session {
    patientId?: string;
    openmrsPatientId?: string;
    error?: string;
    user: DefaultSession["user"];
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    patientId?: string;
    openmrsPatientId?: string;
    accessToken?: string;
    refreshToken?: string;
    accessTokenExpires?: number; // epoch ms
    error?: string;
  }
}

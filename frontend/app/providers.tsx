"use client";

import { SessionProvider } from "next-auth/react";

// Client provider seam. SessionProvider powers useSession() in client components
// (Unit 4's chat header, etc.). signIn() works without it, but useSession needs it.
export function Providers({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}

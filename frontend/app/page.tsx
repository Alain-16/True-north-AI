import { redirect } from "next/navigation";
import { auth } from "@/auth";

// Root: send authenticated users to the app, everyone else to login.
export default async function Home() {
  const session = await auth();
  redirect(session ? "/chat" : "/login");
}

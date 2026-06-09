import { Hero } from "@/components/login/Hero";
import { LoginForm } from "@/components/login/LoginForm";

export default function LoginPage() {
  return (
    <div className="min-h-dvh flex" data-screen="sign-in">
      <Hero />
      <LoginForm />
    </div>
  );
}

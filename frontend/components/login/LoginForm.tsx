"use client";

import { useEffect, useState } from "react";
import {
  ShieldPlus,
  ShieldCheck,
  Mail,
  Phone,
  ArrowRight,
  Check,
  Globe,
  ChevronDown,
  ChevronLeft,
  HeartPulse,
  Loader2,
} from "lucide-react";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
} from "@/components/ui/input-otp";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";

type Step = "request" | "verify";

// Adapted from the Sign In mockup to our real backend flow:
//   Step 1 (request): phone + email  ->  POST /auth/request-otp (emails a 6-digit code)
//   Step 2 (verify):  6-digit code   ->  /auth/verify-otp (issues access + refresh)
// Dropped from the mockup (not in our backend): password, Patient-ID login, SMS,
// magic-link, staff SSO, fingerprint, remember-me.

function Field({
  id,
  icon,
  label,
  hint,
  type = "text",
  placeholder,
  value,
  onChange,
  inputMode,
  autoComplete,
}: {
  id: string;
  icon: React.ReactNode;
  label: string;
  hint?: React.ReactNode;
  type?: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  inputMode?: "text" | "tel" | "email" | "numeric";
  autoComplete?: string;
}) {
  return (
    <div className="block">
      <div className="text-[12.5px] font-semibold text-ink-600 mb-1.5 flex items-center justify-between">
        <label htmlFor={id}>{label}</label>
        {hint && <span className="text-ink-400 font-medium">{hint}</span>}
      </div>
      <div className="field h-12 px-3.5 rounded-xl bg-white border border-ink-200 flex items-center gap-2.5 transition-shadow">
        <span className="text-ink-400 shrink-0">{icon}</span>
        <input
          id={id}
          type={type}
          inputMode={inputMode}
          autoComplete={autoComplete}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 text-[15px] text-ink-800 placeholder:text-ink-400 min-w-0"
        />
      </div>
    </div>
  );
}

export function LoginForm() {
  const [step, setStep] = useState<Step>("request");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resendIn, setResendIn] = useState(0);
  const router = useRouter();

  // Resend countdown tick.
  useEffect(() => {
    if (resendIn <= 0) return;
    const t = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [resendIn]);

  async function requestCode() {
    // BFF → FastAPI /auth/request-otp. Generic response (anti-enumeration).
    await fetch("/api/auth/request-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, email }),
    });
  }

  async function handleRequest(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!phone.trim() || !email.trim()) {
      setError("Enter both your phone number and email.");
      return;
    }
    setSubmitting(true);
    try {
      await requestCode();
      setStep("verify");
      setResendIn(30);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResend() {
    if (resendIn > 0) return;
    setError(null);
    setSubmitting(true);
    try {
      await requestCode();
      setResendIn(30);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (code.length < 6) {
      setError("Enter the 6-digit code.");
      return;
    }
    setSubmitting(true);
    try {
      // signIn → Auth.js Credentials authorize() → FastAPI /auth/verify-otp.
      const res = await signIn("credentials", { phone, code, redirect: false });
      if (res?.error) {
        setError("That code is invalid or has expired.");
      } else {
        router.push("/chat");
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex-1 min-w-0 flex flex-col bg-ink-50">
      {/* top utility bar */}
      <div className="px-6 lg:px-10 pt-6 flex items-center justify-between text-[13px]">
        {/* mobile brand (hero is hidden < lg) */}
        <div className="lg:hidden flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-teal-700 text-white flex items-center justify-center">
            <ShieldPlus size={18} strokeWidth={1.75} />
          </div>
          <div className="leading-tight">
            <div className="text-[14px] font-bold text-ink-900">
              TrueNorth-AI
            </div>
            <div className="text-[11px] text-ink-500">
              St. Mary&apos;s Hospital
            </div>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            className="h-9 px-3 rounded-lg hover:bg-white text-ink-600 inline-flex items-center gap-1.5 font-medium transition cursor-pointer"
          >
            <Globe size={16} strokeWidth={1.75} />
            <span>English</span>
            <ChevronDown size={14} className="text-ink-400" />
          </button>
          <span className="w-px h-5 bg-ink-200 mx-1" />
          <span className="text-ink-500 hidden sm:inline">
            Trouble signing in?
          </span>
          <a
            href="#"
            className="h-9 px-3 rounded-lg text-teal-700 font-semibold hover:bg-teal-50 transition inline-flex items-center"
          >
            Get help
          </a>
        </div>
      </div>

      {/* centered form */}
      <div className="flex-1 flex items-center justify-center px-6 lg:px-10 py-10">
        <div className="w-full max-w-[440px]">
          {/* heading */}
          <div className="mb-7">
            <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-teal-700 bg-teal-50 ring-1 ring-teal-100 rounded-full px-2.5 py-1">
              <HeartPulse size={14} strokeWidth={2} />
              <span>Welcome back</span>
            </span>
            <h1 className="mt-4 text-[30px] font-extrabold text-ink-900 tracking-tight leading-tight text-balance">
              Sign in to TrueNorth-AI
            </h1>
            <p className="mt-2 text-[14.5px] text-ink-500 leading-relaxed">
              {step === "request"
                ? "Pick up your conversation, check results, or book an appointment."
                : "Enter the 6-digit code we just emailed you."}
            </p>
          </div>

          {/* care-provider context (static) */}
          <div className="w-full mb-5 px-4 py-3 rounded-xl bg-white border border-ink-200 flex items-center gap-3 text-left">
            <span className="w-9 h-9 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center shrink-0">
              <ShieldPlus size={18} strokeWidth={1.75} />
            </span>
            <span className="flex-1 min-w-0">
              <span className="block text-[11.5px] font-semibold uppercase tracking-wide text-ink-400">
                Care provider
              </span>
              <span className="block text-[14px] font-semibold text-ink-800 truncate">
                St. Mary&apos;s Hospital · Lagos
              </span>
            </span>
          </div>

          {error && (
            <div
              role="alert"
              aria-live="assertive"
              className="mb-4 rounded-xl bg-crit-50 ring-1 ring-crit-100 px-3.5 py-2.5 text-[13px] text-crit-600 font-medium"
            >
              {error}
            </div>
          )}

          {step === "request" ? (
            <form onSubmit={handleRequest} className="space-y-4">
              <Field
                id="phone"
                icon={<Phone size={18} strokeWidth={1.75} />}
                label="Phone number"
                hint="Linked to your patient record"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                placeholder="+234 ••• ••• ••••"
                value={phone}
                onChange={setPhone}
              />
              <Field
                id="email"
                icon={<Mail size={18} strokeWidth={1.75} />}
                label="Email"
                hint="Where we send your code"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={setEmail}
              />

              <div className="rounded-xl bg-info-50 ring-1 ring-info-100 px-3.5 py-3 text-[13px] text-ink-700 leading-relaxed flex items-start gap-2.5">
                <span className="mt-0.5 text-info-600">
                  <ShieldCheck size={14} strokeWidth={2} />
                </span>
                <span>
                  We&apos;ll email you a 6-digit code. It expires in 10 minutes
                  — phone and email must match your hospital record.
                </span>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full h-12 rounded-xl bg-teal-700 hover:bg-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white text-[15px] font-semibold inline-flex items-center justify-center gap-2 transition shadow-card cursor-pointer"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    Send verification code
                    <ArrowRight size={16} strokeWidth={2} />
                  </>
                )}
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerify} className="space-y-5">
              <button
                type="button"
                onClick={() => {
                  setStep("request");
                  setCode("");
                  setError(null);
                }}
                className="inline-flex items-center gap-1 text-[13px] font-semibold text-ink-500 hover:text-ink-700 transition cursor-pointer"
              >
                <ChevronLeft size={16} />
                Back
              </button>

              <p className="text-[13.5px] text-ink-600">
                Code sent to{" "}
                <span className="font-semibold text-ink-800">{email}</span>
              </p>

              <InputOTP
                maxLength={6}
                value={code}
                onChange={setCode}
                containerClassName="justify-center"
                aria-label="6-digit verification code"
              >
                <InputOTPGroup className="gap-2">
                  {[0, 1, 2, 3, 4, 5].map((i) => (
                    <InputOTPSlot
                      key={i}
                      index={i}
                      className="w-12 h-14 text-[18px] font-semibold rounded-xl border-ink-200"
                    />
                  ))}
                </InputOTPGroup>
              </InputOTP>

              <button
                type="submit"
                disabled={submitting}
                className="w-full h-12 rounded-xl bg-teal-700 hover:bg-teal-800 disabled:opacity-60 disabled:cursor-not-allowed text-white text-[15px] font-semibold inline-flex items-center justify-center gap-2 transition shadow-card cursor-pointer"
              >
                {submitting ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <>
                    Verify &amp; sign in
                    <Check size={16} strokeWidth={2.5} />
                  </>
                )}
              </button>

              <div className="text-center text-[13px] text-ink-500">
                {resendIn > 0 ? (
                  <span>
                    Resend code in{" "}
                    <span className="font-semibold tabular-nums">
                      {resendIn}s
                    </span>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={handleResend}
                    className="font-semibold text-teal-700 hover:underline cursor-pointer"
                  >
                    Resend code
                  </button>
                )}
              </div>
            </form>
          )}

          {/* trust footer */}
          <div className="mt-8 pt-5 border-t border-ink-200">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11.5px] text-ink-500">
              <span className="inline-flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-ink-500" />
                <span className="font-medium">256-bit encrypted</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-teal-700" />
                <span className="font-medium">HIPAA &amp; NDPR compliant</span>
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Check size={14} className="text-teal-700" />
                <span className="font-medium">Audit-logged</span>
              </span>
            </div>
            <p className="mt-3 text-[11.5px] text-ink-400 leading-relaxed">
              By signing in you agree to our{" "}
              <a className="underline hover:text-ink-600" href="#">
                Terms
              </a>{" "}
              and acknowledge our{" "}
              <a className="underline hover:text-ink-600" href="#">
                Privacy Notice
              </a>
              . TrueNorth-AI is a clinical-assistance tool — it doesn&apos;t
              replace your doctor.
            </p>
          </div>
        </div>
      </div>

      {/* bottom support strip */}
      <div className="px-6 lg:px-10 pb-5 text-[12px] text-ink-500 flex flex-wrap items-center justify-between gap-2">
        <span>© 2026 St. Mary&apos;s Hospital · Powered by TrueNorth-AI</span>
        <span className="inline-flex items-center gap-3">
          <a href="#" className="hover:text-ink-700">
            Help
          </a>
          <a href="#" className="hover:text-ink-700">
            Contact support
          </a>
          <a
            href="#"
            className="hover:text-ink-700 font-semibold text-crit-600"
          >
            Medical emergency? Call 199
          </a>
        </span>
      </div>
    </main>
  );
}

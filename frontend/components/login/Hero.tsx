import { ShieldPlus, Sparkles, Check } from "lucide-react";

// Left marketing panel from the Sign In mockup. Static/presentational → server component.
// Hospital name and version are placeholders to parametrize later.
const FEATURES = [
  "Book and reschedule with any department in seconds",
  "Read plain-language summaries of your lab reports",
  "Get triage guidance 24/7 from a clinician-trained model",
];

export function Hero() {
  return (
    <aside className="hidden lg:flex relative flex-col w-[42%] xl:w-[44%] shrink-0 text-white hero-bg overflow-hidden">
      <div className="absolute inset-0 hero-grid pointer-events-none" />
      {/* glow blobs */}
      <div className="absolute -top-32 -left-24 w-[420px] h-[420px] rounded-full bg-teal-500/25 blur-3xl" />
      <div className="absolute -bottom-32 -right-24 w-[440px] h-[440px] rounded-full bg-teal-700/40 blur-3xl" />

      {/* brand */}
      <div className="relative px-12 pt-10 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-white/12 backdrop-blur ring-1 ring-white/15 flex items-center justify-center">
            <ShieldPlus size={20} strokeWidth={1.75} />
          </div>
          <div className="leading-tight">
            <div className="text-[16px] font-bold tracking-tight">
              TrueNorth-AI
            </div>
            <div className="text-[11.5px] text-teal-100/80 font-medium">
              St. Mary&apos;s Hospital
            </div>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-teal-100/90 bg-white/10 ring-1 ring-white/15 rounded-full px-2.5 py-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 pulse-soft" />
          Systems online
        </span>
      </div>

      {/* copy */}
      <div className="relative px-12 mt-16 flex-1 flex flex-col">
        <span className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-teal-100 bg-white/10 ring-1 ring-white/15 rounded-full px-2.5 py-1 self-start">
          <Sparkles size={16} strokeWidth={1.75} />
          <span>AI health assistant · v2.4</span>
        </span>

        <h1 className="mt-5 text-[44px] xl:text-[48px] leading-[1.05] font-extrabold tracking-tight text-balance">
          Care that&apos;s always
          <br />
          just one message away.
        </h1>

        <p className="mt-5 text-[15.5px] leading-relaxed text-teal-50/85 max-w-md">
          Book appointments, review your lab results, and ask questions about
          your care — securely, in your own language.
        </p>

        <ul className="mt-10 space-y-3.5 max-w-md">
          {FEATURES.map((t) => (
            <li
              key={t}
              className="flex items-start gap-3 text-[14.5px] text-teal-50"
            >
              <span className="mt-0.5 w-6 h-6 rounded-full bg-teal-500/25 ring-1 ring-teal-300/40 text-teal-100 flex items-center justify-center shrink-0">
                <Check size={14} strokeWidth={2} />
              </span>
              <span>{t}</span>
            </li>
          ))}
        </ul>

        {/* testimonial */}
        <div className="mt-auto mb-10">
          <figure className="rounded-2xl bg-white/8 backdrop-blur ring-1 ring-white/15 p-5 max-w-md">
            <blockquote className="text-[15px] leading-relaxed text-teal-50">
              &ldquo;I scheduled my mother&apos;s follow-up at 11 PM, in Yoruba,
              without calling anyone. It just worked.&rdquo;
            </blockquote>
            <figcaption className="mt-3 flex items-center gap-2.5">
              <span className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-300 to-teal-500 text-teal-900 flex items-center justify-center text-[12px] font-bold">
                FA
              </span>
              <span className="leading-tight">
                <span className="block text-[13px] font-semibold text-white">
                  Funke A.
                </span>
                <span className="block text-[11.5px] text-teal-100/75">
                  Patient · using TrueNorth-AI for 7 months
                </span>
              </span>
            </figcaption>
          </figure>
        </div>
      </div>
    </aside>
  );
}

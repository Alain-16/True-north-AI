"use client";

import { useState } from "react";
import { Search, Calendar, FileText, Users, History, ChevronRight } from "lucide-react";
import {
  getAppointments,
  getReports,
  getHistory,
  getQueue,
  type AppointmentItem,
  type ReportItem,
  type HistoryResponse,
  type QueueResponse,
} from "@/lib/api-client";
import { usePanel } from "@/hooks/usePanel";
import { AppointmentDetailModal } from "@/components/chat/AppointmentDetailModal";
import { ReportDetailModal } from "@/components/chat/ReportDetailModal";

function SectionCard({
  icon,
  title,
  accent,
  defaultOpen = true,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  accent: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-xl shadow-card ring-1 ring-ink-150">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2.5 px-3.5 py-3 text-left hover:bg-ink-50/60 rounded-xl transition cursor-pointer"
      >
        <span className={`w-7 h-7 rounded-lg flex items-center justify-center ${accent}`}>{icon}</span>
        <span className="flex-1 text-[13.5px] font-semibold text-ink-800">{title}</span>
        <ChevronRight
          size={16}
          className={`text-ink-400 transition-transform ${open ? "rotate-90" : ""}`}
        />
      </button>
      {open && <div className="px-3 pb-3 pt-0.5">{children}</div>}
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return <div className="px-2.5 py-4 text-[12.5px] text-ink-400 text-center">{label}</div>;
}

function LoadingRows() {
  return (
    <div className="px-2.5 py-3 space-y-2">
      <div className="h-3 rounded bg-ink-100 animate-pulse" />
      <div className="h-3 w-2/3 rounded bg-ink-100 animate-pulse" />
    </div>
  );
}

function ErrorState() {
  return (
    <div className="px-2.5 py-4 text-[12.5px] text-destructive text-center">
      Couldn’t load — try again later
    </div>
  );
}

// Render helper: loading → error → content (content decides its own empty state).
function PanelBody<T>({
  state,
  render,
}: {
  state: { data: T | null; loading: boolean; error: boolean };
  render: (data: T) => React.ReactNode;
}) {
  if (state.loading) return <LoadingRows />;
  if (state.error || !state.data) return <ErrorState />;
  return <>{render(state.data)}</>;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function AppointmentsPanel() {
  const state = usePanel<{ items: AppointmentItem[] }>(getAppointments);
  const [selected, setSelected] = useState<AppointmentItem | null>(null);
  return (
    <>
      <PanelBody
        state={state}
        render={({ items }) => {
          const upcoming = items.filter((a) => a.is_upcoming);
          if (upcoming.length === 0) return <EmptyState label="No upcoming appointments" />;
          return (
            <ul className="space-y-1.5">
              {upcoming.map((a) => (
                <li key={a.id}>
                  <button
                    onClick={() => setSelected(a)}
                    className="w-full text-left rounded-lg px-2.5 py-2 hover:bg-ink-50/70 transition cursor-pointer"
                  >
                    <div className="text-[13px] font-medium text-ink-800">
                      {a.doctor_name ?? a.specialty ?? "Appointment"}
                    </div>
                    <div className="text-[12px] text-ink-500">
                      {a.specialty && a.doctor_name ? `${a.specialty} · ` : ""}
                      {fmtDate(a.scheduled_at)}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          );
        }}
      />
      <AppointmentDetailModal
        item={selected}
        onOpenChange={(open) => !open && setSelected(null)}
      />
    </>
  );
}

function ReportsPanel() {
  const state = usePanel<{ items: ReportItem[] }>(getReports);
  const [selected, setSelected] = useState<ReportItem | null>(null);
  return (
    <>
      <PanelBody
        state={state}
        render={({ items }) => {
          if (items.length === 0) return <EmptyState label="No recent reports" />;
          return (
            <ul className="space-y-1.5">
              {items.slice(0, 6).map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setSelected(r)}
                    className="w-full text-left rounded-lg px-2.5 py-2 hover:bg-ink-50/70 transition cursor-pointer"
                  >
                    <div className="text-[13px] font-medium text-ink-800 capitalize">
                      {r.resource_type.replace(/_/g, " ")}
                    </div>
                    {r.ai_explanation_summary && (
                      <div className="text-[12px] text-ink-500 line-clamp-2">
                        {r.ai_explanation_summary}
                      </div>
                    )}
                    <div className="text-[11px] text-ink-400 mt-0.5">{fmtDate(r.created_at)}</div>
                  </button>
                </li>
              ))}
            </ul>
          );
        }}
      />
      <ReportDetailModal item={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </>
  );
}

function QueuePanel() {
  const state = usePanel<QueueResponse>(getQueue);
  return (
    <PanelBody
      state={state}
      render={(q) =>
        q.available && q.position != null ? (
          <div className="px-2.5 py-3">
            <div className="text-[20px] font-semibold text-teal-700">#{q.position}</div>
            {q.estimated_wait_minutes != null && (
              <div className="text-[12px] text-ink-500">
                ~{q.estimated_wait_minutes} min wait
              </div>
            )}
          </div>
        ) : (
          <EmptyState label={q.message} />
        )
      }
    />
  );
}

function HistoryPanel() {
  const state = usePanel<HistoryResponse>(getHistory);
  return (
    <PanelBody
      state={state}
      render={(h) => {
        if (!h.available || !h.context) return <EmptyState label="No medical history yet" />;
        const c = h.context;
        const meds = c.active_medications ?? [];
        const conditions = c.conditions ?? [];
        const allergies = c.allergies ?? [];
        const labs = c.recent_lab_results ?? [];
        if (!meds.length && !conditions.length && !allergies.length && !labs.length)
          return <EmptyState label="No medical history yet" />;
        return (
          <div className="px-2.5 py-1.5 space-y-2 text-[12.5px]">
            {meds.length > 0 && (
              <div>
                <div className="text-ink-400 text-[11px] uppercase tracking-wide">Medications</div>
                <div className="text-ink-700">
                  {meds.map((m) => m.name).filter(Boolean).join(", ")}
                </div>
              </div>
            )}
            {conditions.length > 0 && (
              <div>
                <div className="text-ink-400 text-[11px] uppercase tracking-wide">Conditions</div>
                <div className="text-ink-700">
                  {conditions.map((x) => x.name).filter(Boolean).join(", ")}
                </div>
              </div>
            )}
            {allergies.length > 0 && (
              <div>
                <div className="text-ink-400 text-[11px] uppercase tracking-wide">Allergies</div>
                <div className="text-ink-700">{allergies.join(", ")}</div>
              </div>
            )}
            {labs.length > 0 && (
              <div className="text-ink-500">{labs.length} recent lab result(s)</div>
            )}
          </div>
        );
      }}
    />
  );
}

export function Sidebar() {
  return (
    <aside className="w-[300px] shrink-0 bg-ink-50 border-r border-ink-150 flex flex-col">
      <div className="px-4 pt-4 pb-3">
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
            <Search size={16} />
          </span>
          <input
            placeholder="Search chats, reports…"
            className="w-full h-10 pl-9 pr-3 rounded-lg bg-white ring-1 ring-ink-150 text-[13.5px] placeholder:text-ink-400 focus:outline-none focus:ring-2 focus:ring-teal-400 transition"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-3">
        <SectionCard icon={<Calendar size={16} />} title="Upcoming Appointments" accent="bg-teal-50 text-teal-700">
          <AppointmentsPanel />
        </SectionCard>
        <SectionCard icon={<FileText size={16} />} title="Recent Reports" accent="bg-info-50 text-info-600">
          <ReportsPanel />
        </SectionCard>
        <SectionCard icon={<Users size={16} />} title="Queue Status" accent="bg-teal-50 text-teal-700">
          <QueuePanel />
        </SectionCard>
        <SectionCard
          icon={<History size={16} />}
          title="Medical History"
          accent="bg-ink-100 text-ink-600"
          defaultOpen={false}
        >
          <HistoryPanel />
        </SectionCard>
      </div>
    </aside>
  );
}

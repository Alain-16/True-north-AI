// Browser-facing API client. These call the Next BFF routes (app/api/*),
// NEVER FastAPI directly — the BFF attaches the access token server-side.

// Structured agent message shape (mirrors the backend's format_for_web payload).
export type AgentMessageType =
  | "text"
  | "appointment_card"
  | "slot_selection"
  | "lab_result"
  | "triage_result"
  | "queue_status";

export interface AgentMessage {
  type: AgentMessageType;
  content: unknown;
  metadata?: Record<string, unknown>;
  actions?: string[];
}

// POST a chat message; returns the raw streaming Response for the caller to read
// as Server-Sent Events. Unit 4's useChatStream hook consumes this.
// `reportId` (optional): when the patient is asking a follow-up about a specific
// delivered report, forward its id so the agent answers grounded in that report.
export async function postChat(message: string, reportId?: string): Promise<Response> {
  return fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, report_id: reportId ?? null }),
  });
}

// ── Side-panel data (Unit 5) ──────────────────────────────────────────
// These mirror the FastAPI features/panels/schemas.py response models.

export interface AppointmentItem {
  id: string;
  doctor_name: string | null;
  specialty: string | null;
  scheduled_at: string;
  status: string | null;
  source: string | null;
  is_upcoming: boolean;
}

export interface ReportItem {
  id: string;
  resource_type: string;
  delivery_status: string | null;
  ai_explanation_summary: string | null;
  delivered_at: string | null;
  patient_acknowledged_at: string | null;
  created_at: string;
}

export interface HistoryResponse {
  available: boolean;
  last_source: string | null;
  updated_at: string | null;
  // Shaped clinical context from reports.service.to_history_context.
  context: {
    active_medications?: { name?: string; dosage?: string }[];
    allergies?: string[];
    conditions?: { name?: string; status?: string }[];
    recent_lab_results?: { test?: string; value?: string; date?: string; flag?: string }[];
  } | null;
}

export interface QueueResponse {
  available: boolean;
  position: number | null;
  estimated_wait_minutes: number | null;
  message: string;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const getAppointments = () =>
  getJson<{ items: AppointmentItem[] }>("/api/panels/appointments");
export const getReports = () =>
  getJson<{ items: ReportItem[] }>("/api/panels/reports");
export const getHistory = () => getJson<HistoryResponse>("/api/panels/history");
export const getQueue = () => getJson<QueueResponse>("/api/panels/queue");

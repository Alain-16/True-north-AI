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
export async function postChat(message: string): Promise<Response> {
  return fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

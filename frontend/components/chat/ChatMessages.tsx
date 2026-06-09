"use client";

import { ShieldPlus, ShieldCheck } from "lucide-react";
import type { ChatMessage } from "@/hooks/useChatStream";

const DISCLAIMER =
  "This information is not a diagnosis. Please consult your healthcare provider.";

function AgentAvatar() {
  return (
    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-teal-600 to-teal-700 text-white flex items-center justify-center shrink-0 shadow-card">
      <ShieldPlus size={18} strokeWidth={1.75} />
    </div>
  );
}

export function AgentBubble({
  children,
  footer = false,
}: {
  children: React.ReactNode;
  footer?: boolean;
}) {
  return (
    <div className="flex gap-3 max-w-[680px]">
      <AgentAvatar />
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-ink-500 mb-1.5">TrueNorth-AI</div>
        <div className="bg-white rounded-2xl rounded-tl-md ring-1 ring-ink-150 shadow-card px-4 py-3 text-[15px] leading-relaxed text-ink-800">
          {children}
        </div>
        {footer && (
          <div className="mt-1.5 text-[12px] text-ink-400 flex items-center gap-1.5">
            <ShieldCheck size={14} /> {DISCLAIMER}
          </div>
        )}
      </div>
    </div>
  );
}

export function PatientBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[520px]">
        <div className="text-[12px] font-semibold text-ink-500 mb-1.5 text-right">You</div>
        <div className="bg-teal-600 text-white rounded-2xl rounded-tr-md px-4 py-3 text-[15px] leading-relaxed shadow-card">
          {children}
        </div>
      </div>
    </div>
  );
}

export function TypingBubble() {
  return (
    <div className="flex gap-3">
      <AgentAvatar />
      <div>
        <div className="text-[12px] font-semibold text-ink-500 mb-1.5">
          TrueNorth-AI <span className="text-ink-300 font-normal ml-1">· typing</span>
        </div>
        <div className="bg-white ring-1 ring-ink-150 rounded-2xl rounded-tl-md px-4 py-3 shadow-card inline-flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-ink-300 animate-bounce [animation-delay:-0.3s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-ink-300 animate-bounce [animation-delay:-0.15s]" />
          <span className="w-1.5 h-1.5 rounded-full bg-ink-300 animate-bounce" />
        </div>
      </div>
    </div>
  );
}

export function SuggestionChips({
  items,
  onPick,
}: {
  items: string[];
  onPick: (s: string) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((s) => (
        <button
          key={s}
          onClick={() => onPick(s)}
          className="px-3.5 py-2 rounded-full bg-white ring-1 ring-ink-150 text-[13.5px] font-medium text-ink-700 hover:ring-teal-300 hover:text-teal-700 hover:bg-teal-50 transition cursor-pointer"
        >
          {s}
        </button>
      ))}
    </div>
  );
}

// One message. Today the agent replies in plain text over chat; the one
// structured type (lab_result/prescription) is event-driven and surfaced in the
// Reports side panel + its detail modal (Unit 6), not inline here. Any
// structured payload's prose still renders gracefully as a fallback.
export function MessageItem({ msg }: { msg: ChatMessage }) {
  if (msg.role === "patient") {
    return <PatientBubble>{String(msg.content)}</PatientBubble>;
  }

  const medical = msg.type === "lab_result" || msg.type === "triage_result";

  if (msg.type === "text") {
    return <AgentBubble footer={medical}>{String(msg.content)}</AgentBubble>;
  }

  // Non-text payloads carry the human-readable prose in `content` (format_for_web).
  const summary =
    typeof msg.content === "string"
      ? msg.content
      : ((msg.content as { summary?: string })?.summary ?? "");
  return <AgentBubble footer={medical}>{summary}</AgentBubble>;
}

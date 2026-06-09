"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, ShieldCheck, FileText, X } from "lucide-react";
import { useChatStream } from "@/hooks/useChatStream";
import { useReportContext } from "@/components/chat/ReportContext";
import {
  AgentBubble,
  MessageItem,
  SuggestionChips,
  TypingBubble,
} from "@/components/chat/ChatMessages";

const WELCOME_SUGGESTIONS = [
  "Book an appointment",
  "Check my lab results",
  "I have a health concern",
];

export function ChatPanel() {
  const { messages, isStreaming, error, sendMessage } = useChatStream();
  const { activeReport, clearReport } = useReportContext();
  const [draft, setDraft] = useState("");
  const scrollerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the newest message / typing indicator.
  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isStreaming]);

  function submit() {
    const text = draft.trim();
    if (!text || isStreaming) return;
    setDraft("");
    void sendMessage(text, activeReport?.id);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <main className="flex-1 min-w-0 flex flex-col bg-ink-50/40">
      {/* context strip */}
      <div className="px-8 py-3 border-b border-ink-150 bg-white flex items-center gap-3">
        <span className="w-8 h-8 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center">
          <Sparkles size={16} strokeWidth={1.75} />
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-semibold text-ink-800">New conversation</div>
          <div className="text-[12px] text-ink-500">TrueNorth-AI · your health assistant</div>
        </div>
      </div>

      {/* conversation */}
      <div ref={scrollerRef} className="flex-1 overflow-y-auto">
        <div className="max-w-[820px] mx-auto px-8 py-8 space-y-6">
          {isEmpty && (
            <AgentBubble>
              <p className="text-ink-800">
                Hello — I&apos;m <strong>TrueNorth-AI</strong>, your health assistant at St.
                Mary&apos;s. How can I help today?
              </p>
              <SuggestionChips
                items={WELCOME_SUGGESTIONS}
                onPick={(s) => void sendMessage(s, activeReport?.id)}
              />
            </AgentBubble>
          )}

          {messages.map((m, i) => (
            <MessageItem key={i} msg={m} />
          ))}

          {isStreaming && <TypingBubble />}

          {error && (
            <div
              role="alert"
              className="max-w-[680px] ml-12 rounded-xl bg-crit-50 ring-1 ring-crit-100 px-4 py-3 text-[13.5px] text-crit-600"
            >
              {error}
            </div>
          )}
        </div>
      </div>

      {/* composer */}
      <div className="px-8 pt-3 pb-6 bg-gradient-to-t from-white via-white to-transparent">
        <div className="max-w-[820px] mx-auto">
          {activeReport && (
            <div className="mb-2 flex items-center gap-2 rounded-lg bg-info-50 ring-1 ring-info-100 px-3 py-2 text-[13px] text-info-600">
              <FileText size={15} className="shrink-0" />
              <span className="flex-1 min-w-0 truncate">
                Asking about <span className="font-semibold">{activeReport.label}</span>
              </span>
              <button
                onClick={clearReport}
                aria-label="Stop asking about this report"
                className="shrink-0 rounded-md p-1 hover:bg-info-100/70 transition cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
          )}
          <div className="bg-white rounded-2xl ring-1 ring-ink-150 shadow-lift flex items-end p-2 gap-1.5">
            <textarea
              rows={1}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder={
                activeReport
                  ? `Ask a question about ${activeReport.label}…`
                  : "Type a message to TrueNorth-AI…"
              }
              className="flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] text-ink-800 placeholder:text-ink-400 focus:outline-none min-h-[44px] max-h-[160px]"
            />
            <button
              onClick={submit}
              disabled={!draft.trim() || isStreaming}
              className="h-11 px-4 rounded-xl bg-teal-700 hover:bg-teal-800 disabled:opacity-50 disabled:cursor-not-allowed text-white inline-flex items-center gap-2 text-[14px] font-semibold shrink-0 transition shadow-card cursor-pointer"
            >
              Send <Send size={16} strokeWidth={2} />
            </button>
          </div>
          <div className="mt-2 flex items-center justify-center gap-1.5 text-[11.5px] text-ink-400">
            <ShieldCheck size={14} />
            <span>Encrypted · Your data stays with St. Mary&apos;s. Not a substitute for a doctor.</span>
          </div>
        </div>
      </div>
    </main>
  );
}

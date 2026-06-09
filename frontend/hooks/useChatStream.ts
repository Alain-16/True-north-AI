"use client";

import { useCallback, useState } from "react";
import { postChat, type AgentMessage } from "@/lib/api-client";

export type ChatMessage =
  | { role: "patient"; type: "text"; content: string }
  | {
      role: "agent";
      type: AgentMessage["type"];
      content: unknown;
      metadata?: Record<string, unknown>;
      actions?: string[];
    };

// Consumes the BFF SSE stream (`data: {token}` / `data: [DONE]` / `data: {error}`).
// Each `token` is a JSON string of the backend's format_for_web message
// ({type, content, metadata, actions}).
export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string, reportId?: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setError(null);
      setMessages((m) => [...m, { role: "patient", type: "text", content: trimmed }]);
      setIsStreaming(true);

      try {
        const res = await postChat(trimmed, reportId);
        if (!res.ok || !res.body) throw new Error("chat request failed");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE frames are separated by a blank line.
          const frames = buffer.split("\n\n");
          buffer = frames.pop() ?? "";

          for (const frame of frames) {
            const line = frame.trim();
            if (!line.startsWith("data:")) continue;
            const payload = line.slice(5).trim();
            if (payload === "[DONE]") continue;

            try {
              const parsed = JSON.parse(payload) as { token?: string; error?: string };
              if (parsed.error) {
                setError("Something went wrong. Please try again.");
                continue;
              }
              if (parsed.token) {
                const msg = JSON.parse(parsed.token) as AgentMessage;
                setMessages((m) => [...m, { role: "agent", ...msg }]);
              }
            } catch {
              // Ignore a partial/garbled frame; the next read may complete it.
            }
          }
        }
      } catch {
        setError("I'm having trouble reaching the hospital system. Please try again.");
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming],
  );

  return { messages, isStreaming, error, sendMessage };
}

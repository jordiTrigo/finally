"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchChat, sendChat } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";

export interface ChatState {
  messages: ChatMessage[];
  pending: boolean;
  error: string | null;
  send: (text: string) => Promise<void>;
}

function localMessage(role: "user" | "assistant", content: string): ChatMessage {
  return {
    id: `local-${role}-${Date.now()}`,
    role,
    content,
    actions: null,
    created_at: new Date().toISOString(),
  };
}

/**
 * Conversation state. History loads once on mount; each reply is appended
 * locally rather than refetched, since the POST returns the whole answer.
 *
 * `onActions` fires when the assistant executed trades or watchlist changes,
 * so the caller can refetch whatever the LLM just changed.
 */
export function useChat(onActions: () => void): ChatState {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchChat()
      .then(setMessages)
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "Chat unavailable"),
      );
  }, []);

  const send = useCallback(
    async (text: string) => {
      setError(null);
      setPending(true);
      setMessages((previous) => [...previous, localMessage("user", text)]);

      try {
        const reply = await sendChat(text);
        setMessages((previous) => [
          ...previous,
          { ...localMessage("assistant", reply.message), actions: reply.actions },
        ]);
        if (reply.actions.length > 0) onActions();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "FinAlly did not reply");
      } finally {
        setPending(false);
      }
    },
    [onActions],
  );

  return { messages, pending, error, send };
}

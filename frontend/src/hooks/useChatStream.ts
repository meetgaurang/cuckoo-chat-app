import { useCallback, useEffect, useRef, useState } from "react";
import type { Message } from "@/types";

// Backend base URL. Defaults to "" so requests hit the same origin
// (Vite dev proxy in development, nginx proxy in the container).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const STORAGE_KEY = "cuckoo-chat-history";

function newId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadHistory(): Message[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Message[]) : [];
  } catch {
    return [];
  }
}

export function useChatStream() {
  const [messages, setMessages] = useState<Message[]>(loadHistory);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Persist conversation client-side (no server-side history).
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      /* ignore quota errors */
    }
  }, [messages]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
  }, []);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;

      setError(null);
      const userMsg: Message = { id: newId(), role: "user", content: trimmed };
      const assistantId = newId();

      // History sent to the backend is the full prior conversation + new turn.
      const history = [...messages, userMsg].map(({ role, content }) => ({ role, content }));

      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: "assistant", content: "" },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`Request failed (${res.status})`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        // Parse the SSE stream frame-by-frame (frames separated by \n\n).
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sep: number;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);

            const line = frame.trim();
            if (!line.startsWith("data:")) continue;
            const payload = line.slice(5).trim();
            if (payload === "[DONE]") continue;

            try {
              const data = JSON.parse(payload) as { delta?: string; error?: string };
              if (data.error) {
                setError(data.error);
              } else if (data.delta) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, content: m.content + data.delta } : m
                  )
                );
              }
            } catch {
              /* ignore malformed frame */
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message || "Something went wrong.");
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
        // Drop an empty assistant bubble (e.g. immediate error/abort).
        setMessages((prev) =>
          prev.filter((m) => !(m.id === assistantId && m.content === ""))
        );
      }
    },
    [messages, isStreaming]
  );

  return { messages, isStreaming, error, send, stop, reset };
}

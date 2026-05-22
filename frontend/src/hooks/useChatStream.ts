/**
 * useChatStream — consumes the POST /chat/ SSE endpoint.
 *
 * Events handled:
 *   {"type": "token",     "content": "..."}   — streamed token
 *   {"type": "citations", "items": [...]}      — final event with cited sources
 *   {"type": "error",     "message": "..."}    — generation error
 *
 * The hook cancels the connection on unmount (or when cancel() is called)
 * to avoid leaving connections open and draining the free-tier quota.
 *
 * Usage:
 *   const {streaming, error, sendMessage, cancel} = useChatStream()
 *   await sendMessage(query, sessionId, {onToken, onCitations, onDone})
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { Citation } from "../api/chat";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface ChatStreamCallbacks {
  onToken: (text: string) => void;
  onCitations: (citations: Citation[]) => void;
  onDone: () => void;
}

export function useChatStream() {
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cancel the active stream on unmount.
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (
      query: string,
      sessionId: string | null,
      callbacks: ChatStreamCallbacks,
    ): Promise<void> => {
      // Cancel any in-flight request before starting a new one.
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      setStreaming(true);
      setError(null);

      try {
        const res = await fetch(`${BASE}/chat/`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, session_id: sessionId }),
          signal: ac.signal,
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const msg =
            typeof body?.detail === "string"
              ? body.detail
              : `HTTP ${res.status}`;
          throw new Error(msg);
        }

        if (!res.body) throw new Error("No response body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE format: lines separated by \n, events separated by \n\n.
          // We split on \n and process complete lines.
          const lines = buffer.split("\n");
          // The last element may be incomplete — keep it in the buffer.
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;

            const payload = trimmed.slice(5).trim();
            if (!payload || payload === "[DONE]") continue;

            try {
              const event = JSON.parse(payload) as {
                type: string;
                content?: string;
                items?: Citation[];
                message?: string;
              };

              if (event.type === "token" && event.content) {
                callbacks.onToken(event.content);
              } else if (event.type === "citations" && event.items) {
                callbacks.onCitations(event.items);
              } else if (event.type === "error") {
                throw new Error(event.message ?? "Generation error");
              }
            } catch (parseErr) {
              // Surface real errors; ignore JSON parse failures on partial lines.
              if (parseErr instanceof Error && parseErr.message !== "Unexpected end of JSON input") {
                throw parseErr;
              }
            }
          }
        }

        callbacks.onDone();
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          // Intentional cancellation — not an error from the user's perspective.
          return;
        }
        const msg = err instanceof Error ? err.message : "Error desconocido";
        setError(msg);
        callbacks.onDone();
      } finally {
        setStreaming(false);
      }
    },
    [],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { streaming, error, sendMessage, cancel };
}

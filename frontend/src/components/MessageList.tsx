/**
 * MessageList — scrollable conversation history.
 *
 * Auto-scrolls to the bottom when new messages arrive or during streaming.
 * Shows a loading indicator before the first token arrives.
 */

import { useEffect, useRef } from "react";
import type { Citation } from "../api/chat";
import Message, { type MessageData } from "./Message";

interface MessageListProps {
  messages: MessageData[];
  loading: boolean; // true = awaiting first token
  /** Receives the 0-based citation index plus the message's own citations array. */
  onCitationClick: (index: number, citations: Citation[]) => void;
}

export default function MessageList({
  messages,
  loading,
  onCitationClick,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever messages change (new content or streaming tokens).
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0 && !loading) {
    return (
      <div style={styles.empty} role="status" aria-label="Vacío">
        <p style={styles.emptyText}>
          Haz una pregunta sobre la documentación de FastAPI.
        </p>
      </div>
    );
  }

  return (
    <div style={styles.list} role="log" aria-live="polite" aria-label="Conversación">
      {messages.map((msg) => (
        <Message key={msg.id} message={msg} onCitationClick={onCitationClick} />
      ))}

      {loading && (
        <div style={styles.loadingRow} role="status" aria-label="Generando respuesta">
          <span style={styles.dot} />
          <span style={styles.dot} />
          <span style={styles.dot} />
        </div>
      )}

      {/* Invisible anchor for auto-scroll */}
      <div ref={bottomRef} />
    </div>
  );
}

const styles = {
  list: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "1rem 0",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.15rem",
  } as React.CSSProperties,

  empty: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  } as React.CSSProperties,

  emptyText: {
    color: "var(--muted)",
    fontSize: "0.95rem",
    textAlign: "center" as const,
    maxWidth: 340,
    lineHeight: 1.6,
  } as React.CSSProperties,

  loadingRow: {
    display: "flex",
    gap: 5,
    padding: "0.35rem 1rem",
  } as React.CSSProperties,

  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: "var(--orange)",
    display: "inline-block",
    animation: "blink 1s ease-in-out infinite",
  } as React.CSSProperties,
};

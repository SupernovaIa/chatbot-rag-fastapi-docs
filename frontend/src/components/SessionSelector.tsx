/**
 * SessionSelector — sidebar listing past sessions for the authenticated user.
 *
 * Sessions are loaded from GET /chat/sessions on mount and whenever
 * refreshTrigger changes (e.g. after a new chat turn is completed).
 *
 * Selecting a session calls onSelectSession so the parent can load history.
 * "Nueva conversación" resets to null (parent creates a fresh UUID on next send).
 */

import { useCallback, useEffect, useState } from "react";
import { deleteSession, listSessions, type SessionOut } from "../api/chat";

interface SessionSelectorProps {
  currentSessionId: string | null;
  onSelectSession: (sessionId: string | null) => void;
  refreshTrigger: number;
}

export default function SessionSelector({
  currentSessionId,
  onSelectSession,
  refreshTrigger,
}: SessionSelectorProps) {
  const [sessions, setSessions] = useState<SessionOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listSessions();
      // Sort descending by updated_at so the most recent is first.
      const sorted = [...data].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
      );
      setSessions(sorted);
    } catch {
      setError("No se pudieron cargar las sesiones");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions, refreshTrigger]);

  const handleDelete = useCallback(
    async (sessionId: string) => {
      if (!window.confirm("¿Borrar esta conversación? No se puede deshacer.")) {
        return;
      }
      try {
        await deleteSession(sessionId);
        // If the deleted session was the active one, reset to a new chat.
        if (sessionId === currentSessionId) {
          onSelectSession(null);
        }
        await fetchSessions();
      } catch {
        setError("No se pudo borrar la conversación");
      }
    },
    [currentSessionId, onSelectSession, fetchSessions],
  );

  return (
    <nav style={styles.nav} aria-label="Sesiones de chat">
      <div style={styles.header}>
        <span style={styles.title}>Conversaciones</span>
      </div>

      <button
        onClick={() => onSelectSession(null)}
        style={{
          ...styles.newBtn,
          ...(currentSessionId === null ? styles.newBtnActive : {}),
        }}
        aria-current={currentSessionId === null ? "page" : undefined}
      >
        + Nueva conversación
      </button>

      <div style={styles.list} role="list">
        {loading && (
          <p style={styles.hint}>Cargando…</p>
        )}
        {!loading && error && (
          <p style={styles.errorText}>{error}</p>
        )}
        {!loading && !error && sessions.length === 0 && (
          <p style={styles.hint}>Sin conversaciones previas</p>
        )}
        {sessions.map((s) => (
          <div
            key={s.id}
            role="listitem"
            style={{
              ...styles.row,
              ...(s.id === currentSessionId ? styles.itemActive : {}),
            }}
          >
            <button
              onClick={() => onSelectSession(s.id)}
              style={styles.item}
              aria-current={s.id === currentSessionId ? "page" : undefined}
              aria-label={`Conversación del ${formatDate(s.updated_at)}`}
            >
              <span style={styles.itemDate}>{formatDate(s.updated_at)}</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(s.id);
              }}
              style={styles.deleteBtn}
              aria-label={`Borrar conversación del ${formatDate(s.updated_at)}`}
              title="Borrar conversación"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </nav>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("es-ES", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const styles = {
  nav: {
    width: 220,
    flexShrink: 0,
    borderRight: "1px solid #dde3e5",
    display: "flex",
    flexDirection: "column" as const,
    background: "#f8fbfc",
    overflowY: "hidden" as const,
  } as React.CSSProperties,

  header: {
    padding: "0.85rem 1rem 0.5rem",
    borderBottom: "1px solid #dde3e5",
  } as React.CSSProperties,

  title: {
    fontSize: "0.75rem",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    color: "var(--muted)",
  } as React.CSSProperties,

  newBtn: {
    margin: "0.5rem 0.6rem",
    padding: "0.45rem 0.75rem",
    background: "none",
    border: "1px solid var(--accent)",
    borderRadius: 6,
    color: "var(--accent)",
    fontSize: "0.85rem",
    fontFamily: "var(--font-sans)",
    fontWeight: 500,
    cursor: "pointer",
    textAlign: "left" as const,
    transition: "background 0.15s",
  } as React.CSSProperties,

  newBtnActive: {
    background: "#e8f2f0",
  } as React.CSSProperties,

  list: {
    flex: 1,
    overflowY: "auto" as const,
    padding: "0.25rem 0.4rem",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.15rem",
  } as React.CSSProperties,

  row: {
    display: "flex",
    alignItems: "center",
    border: "1px solid transparent",
    borderRadius: 6,
    transition: "background 0.12s",
  } as React.CSSProperties,

  item: {
    flex: 1,
    minWidth: 0,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "flex-start",
    padding: "0.5rem 0.65rem",
    background: "none",
    border: "none",
    cursor: "pointer",
    textAlign: "left" as const,
    fontFamily: "var(--font-sans)",
  } as React.CSSProperties,

  deleteBtn: {
    flexShrink: 0,
    width: 26,
    height: 26,
    marginRight: "0.3rem",
    padding: 0,
    background: "none",
    border: "none",
    borderRadius: 4,
    color: "var(--muted)",
    fontSize: "1.1rem",
    lineHeight: 1,
    cursor: "pointer",
    fontFamily: "var(--font-sans)",
  } as React.CSSProperties,

  itemActive: {
    background: "#e8f2f0",
    borderColor: "var(--highlight)",
  } as React.CSSProperties,

  itemDate: {
    fontSize: "0.8rem",
    color: "var(--muted)",
  } as React.CSSProperties,

  hint: {
    margin: "0.5rem 0.65rem",
    fontSize: "0.8rem",
    color: "var(--muted)",
  } as React.CSSProperties,

  errorText: {
    margin: "0.5rem 0.65rem",
    fontSize: "0.8rem",
    color: "var(--danger)",
  } as React.CSSProperties,
};

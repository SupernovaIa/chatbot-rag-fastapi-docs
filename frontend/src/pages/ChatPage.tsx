/**
 * ChatPage — the main protected chat interface.
 *
 * Layout:
 *   ┌──────────────┬──────────────────────────────────────┐
 *   │ SessionSel.  │  MessageList                         │
 *   │ (sidebar)    │                                      │
 *   │              ├──────────────────────────────────────┤
 *   │              │  ChatInput                           │
 *   └──────────────┴──────────────────────────────────────┘
 *   CitationsPanel slides in from the right when a citation chip is clicked.
 *
 * Session lifecycle:
 *   - currentSessionId === null  → next send creates a new session on the
 *     backend using a client-generated UUID (crypto.randomUUID). This UUID
 *     is set as currentSessionId immediately so subsequent turns reuse it.
 *   - onSelectSession(id)        → loads history from GET /chat/sessions/{id}
 *     and restores messages array.
 *   - After each completed turn, refreshTrigger increments so SessionSelector
 *     re-fetches the list (picks up newly created sessions, reorders by updated_at).
 */

import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type Citation, getSession } from "../api/chat";
import ChatInput from "../components/ChatInput";
import CitationsPanel from "../components/CitationsPanel";
import MessageList from "../components/MessageList";
import SessionSelector from "../components/SessionSelector";
import { type MessageData } from "../components/Message";
import { useChatStream } from "../hooks/useChatStream";
import { useAuth } from "../hooks/useAuth";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function newId(): string {
  return crypto.randomUUID();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ChatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { streaming, error: streamError, sendMessage } = useChatStream();

  const [messages, setMessages] = useState<MessageData[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false); // waiting for first token
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);
  const [activeCitations, setActiveCitations] = useState<Citation[]>([]);

  // Track the streaming assistant message id so we can update it.
  const streamingMsgIdRef = useRef<string | null>(null);

  // ── Logout ──────────────────────────────────────────────────────────────

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  // ── Load session history ─────────────────────────────────────────────────

  const loadSession = useCallback(async (sessionId: string) => {
    try {
      const detail = await getSession(sessionId);
      // Rebuild messages array from history.
      const rebuilt: MessageData[] = [];
      // Messages come as turn_idx/role/content/citations pairs. Group by turn.
      for (const msg of detail.messages) {
        rebuilt.push({
          id: `${sessionId}-${msg.turn_idx}-${msg.role}`,
          role: msg.role as "user" | "assistant",
          content: msg.content,
          citations: msg.citations as Citation[],
        });
      }
      setMessages(rebuilt);
    } catch {
      setMessages([]);
    }
  }, []);

  const handleSelectSession = useCallback(
    (sessionId: string | null) => {
      setCurrentSessionId(sessionId);
      setSelectedCitationIndex(null);
      setActiveCitations([]);
      if (sessionId) {
        loadSession(sessionId);
      } else {
        setMessages([]);
      }
    },
    [loadSession],
  );

  // ── Citation panel ────────────────────────────────────────────────────────

  /**
   * Opens the CitationsPanel for a specific message's citations.
   * `citations` comes directly from the clicked message — no global search.
   */
  function handleCitationClick(index: number, citations: Citation[]) {
    setActiveCitations(citations);
    setSelectedCitationIndex(index);
  }

  // ── Send message ─────────────────────────────────────────────────────────

  async function handleSend(text: string) {
    if (streaming) return;

    // Resolve or create session UUID.
    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = newId();
      setCurrentSessionId(sessionId);
    }

    // Append user message.
    const userMsgId = newId();
    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: text },
    ]);

    // Append empty streaming assistant message.
    const assistantMsgId = newId();
    streamingMsgIdRef.current = assistantMsgId;
    setMessages((prev) => [
      ...prev,
      { id: assistantMsgId, role: "assistant", content: "", isStreaming: true },
    ]);

    setLoading(true);
    setSelectedCitationIndex(null);

    await sendMessage(text, sessionId, {
      onToken(token) {
        setLoading(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + token }
              : m,
          ),
        );
      },
      onCitations(citations) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, citations, isStreaming: false }
              : m,
          ),
        );
        // Refresh session list so new session appears in sidebar.
        setRefreshTrigger((n) => n + 1);
      },
      onDone() {
        setLoading(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m,
          ),
        );
        setRefreshTrigger((n) => n + 1);
        streamingMsgIdRef.current = null;
      },
    });
  }

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={styles.page}>
      {/* ── Header ── */}
      <header style={styles.header}>
        <h1 style={styles.title}>
          <span style={styles.titleAccent}>RAG</span> FastAPI docs
        </h1>
        <div style={styles.userBar}>
          {streamError && (
            <span style={styles.errorBadge} role="alert">
              {streamError}
            </span>
          )}
          <span style={styles.email} aria-label={`Usuario: ${user?.email}`}>
            {user?.email}
          </span>
          <button
            onClick={handleLogout}
            style={styles.logoutBtn}
            aria-label="Cerrar sesión"
          >
            Salir
          </button>
        </div>
      </header>

      {/* ── Body ── */}
      <div style={styles.body}>
        {/* Sidebar */}
        <SessionSelector
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          refreshTrigger={refreshTrigger}
        />

        {/* Chat area */}
        <div style={styles.chatArea}>
          <MessageList
            messages={messages}
            loading={loading}
            onCitationClick={handleCitationClick}
          />
          <ChatInput onSend={handleSend} disabled={streaming} />
        </div>
      </div>

      {/* Citations slide-in panel */}
      <CitationsPanel
        citations={activeCitations}
        selectedIndex={selectedCitationIndex}
        onClose={() => setSelectedCitationIndex(null)}
        onSelectIndex={setSelectedCitationIndex}
      />
    </div>
  );
}

const styles = {
  page: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100vh",
    overflow: "hidden" as const,
    fontFamily: "var(--font-sans)",
    background: "var(--bg)",
    color: "var(--fg)",
  } as React.CSSProperties,

  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.65rem 1.25rem",
    borderBottom: "1px solid #dde3e5",
    background: "var(--bg)",
    flexShrink: 0,
  } as React.CSSProperties,

  title: {
    margin: 0,
    fontSize: "1.05rem",
    fontWeight: 600,
    color: "var(--fg)",
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
  } as React.CSSProperties,

  titleAccent: {
    background: "var(--accent)",
    color: "#fff",
    borderRadius: 4,
    padding: "0.05em 0.4em",
    fontSize: "0.9em",
    fontWeight: 600,
    letterSpacing: "0.03em",
  } as React.CSSProperties,

  userBar: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
  } as React.CSSProperties,

  email: {
    fontSize: "0.825rem",
    color: "var(--muted)",
  } as React.CSSProperties,

  errorBadge: {
    fontSize: "0.8rem",
    color: "var(--danger)",
    background: "#fdf0f0",
    border: "1px solid var(--danger)",
    borderRadius: 4,
    padding: "0.15rem 0.5rem",
    maxWidth: 240,
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
  } as React.CSSProperties,

  logoutBtn: {
    padding: "0.3rem 0.7rem",
    background: "transparent",
    border: "1px solid #c8d5d8",
    borderRadius: 5,
    cursor: "pointer",
    fontSize: "0.825rem",
    color: "var(--muted)",
    fontFamily: "var(--font-sans)",
    transition: "border-color 0.15s, color 0.15s",
  } as React.CSSProperties,

  body: {
    flex: 1,
    display: "flex",
    overflow: "hidden" as const,
    minHeight: 0,
  } as React.CSSProperties,

  chatArea: {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden" as const,
    minWidth: 0,
  } as React.CSSProperties,
};

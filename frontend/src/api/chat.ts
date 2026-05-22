/**
 * Chat API — session listing and history.
 *
 * Streaming is handled by useChatStream, not here.
 * All requests include credentials so the httpOnly cookie is forwarded.
 */

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Citation {
  source: string;
  section: string;
  chunk_hash: string;
  /** Raw text of the retrieved documentation chunk. Present on live turns
   *  and on sessions loaded from history (stored in the citations JSONB). */
  content?: string;
}

export interface SessionOut {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface MessageOut {
  turn_idx: number;
  role: string;
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface SessionDetailOut {
  id: string;
  created_at: string;
  updated_at: string;
  messages: MessageOut[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** GET /chat/sessions — lists all sessions for the authenticated user. */
export async function listSessions(): Promise<SessionOut[]> {
  const res = await fetch(`${BASE}/chat/sessions`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** GET /chat/sessions/{id} — full message history for a session. */
export async function getSession(sessionId: string): Promise<SessionDetailOut> {
  const res = await fetch(`${BASE}/chat/sessions/${sessionId}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

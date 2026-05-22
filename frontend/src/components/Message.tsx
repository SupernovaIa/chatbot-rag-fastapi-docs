/**
 * Message — renders a single chat message.
 *
 * User messages are shown as plain text (right-aligned).
 * Assistant messages are rendered as Markdown with rehype-sanitize to prevent
 * XSS from corpus content (spec 11). When citations are available, [N] patterns
 * become clickable chips that trigger CitationsPanel.
 *
 * States:
 *   isStreaming=true  → blinking cursor appended; no citation chips yet.
 *   citations present → [N] patterns are replaced by clickable chips.
 */

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Citation } from "../api/chat";

export interface MessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

interface MessageProps {
  message: MessageData;
  onCitationClick: (index: number) => void;
}

// Components override for react-markdown: strip wrapping <p> inside inline
// segments so we don't produce invalid nested block elements when splitting
// by citation markers.
const inlineComponents = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  p: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
};

/**
 * Splits text on [N] citation markers and returns an array of React nodes:
 * text segments rendered through ReactMarkdown and [N] patterns as buttons.
 */
function renderWithCitationChips(
  text: string,
  citations: Citation[],
  onCitationClick: (idx: number) => void,
): React.ReactNode[] {
  const parts = text.split(/(\[\d+\])/);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      const n = parseInt(m[1], 10);
      const citIdx = n - 1;
      const hasCitation = citIdx >= 0 && citIdx < citations.length;
      return (
        <button
          key={i}
          className="citation-chip"
          onClick={() => hasCitation && onCitationClick(citIdx)}
          disabled={!hasCitation}
          aria-label={`Ver cita ${n}`}
        >
          [{n}]
        </button>
      );
    }
    if (!part) return null;
    return (
      <ReactMarkdown
        key={i}
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={inlineComponents as object}
      >
        {part}
      </ReactMarkdown>
    );
  });
}

export default function Message({ message, onCitationClick }: MessageProps) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div style={{ ...styles.row, justifyContent: "flex-end" }}>
        <div style={styles.userBubble}>
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  const hasCitations = Boolean(message.citations && message.citations.length > 0);
  const showChips = hasCitations && !message.isStreaming;

  return (
    <div style={{ ...styles.row, justifyContent: "flex-start" }}>
      <div style={styles.assistantBubble}>
        <div className="prose" style={styles.prose}>
          {showChips ? (
            renderWithCitationChips(
              message.content,
              message.citations!,
              onCitationClick,
            )
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
            >
              {message.content}
            </ReactMarkdown>
          )}
          {message.isStreaming && <span className="streaming-cursor" aria-hidden="true" />}
        </div>
      </div>
    </div>
  );
}

const styles = {
  row: {
    display: "flex",
    padding: "0.35rem 1rem",
  } as React.CSSProperties,

  userBubble: {
    maxWidth: "70%",
    background: "#eef6f3",
    color: "var(--fg)",
    borderRadius: "12px 12px 2px 12px",
    padding: "0.55rem 0.85rem",
    fontSize: "0.95rem",
    lineHeight: 1.5,
    whiteSpace: "pre-wrap" as const,
    wordBreak: "break-word" as const,
  } as React.CSSProperties,

  assistantBubble: {
    maxWidth: "85%",
    background: "transparent",
  } as React.CSSProperties,

  prose: {
    fontSize: "0.95rem",
  } as React.CSSProperties,
};

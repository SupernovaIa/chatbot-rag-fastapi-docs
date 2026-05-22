/**
 * ChatInput — textarea + send button.
 *
 * - Disabled (and visually marked) while streaming is in progress.
 * - Sends on Enter (without Shift), inserts newline on Shift+Enter.
 * - Accessible: button has aria-label, input has proper label.
 */

import { type FormEvent, type KeyboardEvent, useRef, useState } from "react";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={styles.form} aria-label="Enviar mensaje">
      <label htmlFor="chat-input" style={styles.srOnly}>
        Escribe tu pregunta
      </label>
      <textarea
        id="chat-input"
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? "Generando respuesta…" : "Escribe una pregunta sobre FastAPI…"}
        rows={2}
        style={{
          ...styles.textarea,
          ...(disabled ? styles.textareaDisabled : {}),
        }}
        aria-disabled={disabled}
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        style={{
          ...styles.button,
          ...(disabled || !value.trim() ? styles.buttonDisabled : {}),
        }}
        aria-label="Enviar"
      >
        {disabled ? (
          <StreamingDot />
        ) : (
          <SendIcon />
        )}
      </button>
    </form>
  );
}

function SendIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function StreamingDot() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        borderRadius: "50%",
        border: "2px solid currentColor",
        borderTopColor: "transparent",
        animation: "spin 0.7s linear infinite",
      }}
      aria-hidden="true"
    />
  );
}

const styles = {
  form: {
    display: "flex",
    gap: "0.5rem",
    padding: "0.75rem 1rem",
    borderTop: "1px solid #dde3e5",
    background: "var(--bg)",
    alignItems: "flex-end",
  } as React.CSSProperties,

  textarea: {
    flex: 1,
    resize: "none" as const,
    border: "1px solid #c8d5d8",
    borderRadius: 8,
    padding: "0.55rem 0.75rem",
    fontFamily: "var(--font-sans)",
    fontSize: "0.95rem",
    color: "var(--fg)",
    background: "var(--bg)",
    lineHeight: 1.5,
    transition: "border-color 0.15s",
    outline: "none",
  } as React.CSSProperties,

  textareaDisabled: {
    background: "#f4f7f8",
    color: "var(--muted)",
    cursor: "not-allowed",
  } as React.CSSProperties,

  button: {
    flexShrink: 0,
    width: 40,
    height: 40,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    cursor: "pointer",
    transition: "opacity 0.15s",
  } as React.CSSProperties,

  buttonDisabled: {
    background: "var(--muted)",
    cursor: "not-allowed",
    opacity: 0.6,
  } as React.CSSProperties,

  srOnly: {
    position: "absolute" as const,
    width: 1,
    height: 1,
    padding: 0,
    margin: -1,
    overflow: "hidden" as const,
    clip: "rect(0,0,0,0)" as const,
    whiteSpace: "nowrap" as const,
    border: 0,
  } as React.CSSProperties,
};

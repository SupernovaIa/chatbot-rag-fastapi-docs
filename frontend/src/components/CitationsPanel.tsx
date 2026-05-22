/**
 * CitationsPanel — displays the source chunk when a citation chip is clicked.
 *
 * Opens as a fixed side panel (right side on desktop).
 * Keyboard-accessible: Escape closes it; focus trapped inside when open.
 */

import { useEffect, useRef } from "react";
import type { Citation } from "../api/chat";

interface CitationsPanelProps {
  citations: Citation[];
  selectedIndex: number | null;
  onClose: () => void;
}

export default function CitationsPanel({
  citations,
  selectedIndex,
  onClose,
}: CitationsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape.
  useEffect(() => {
    if (selectedIndex === null) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selectedIndex, onClose]);

  // Auto-focus the panel when it opens so screen readers announce it.
  useEffect(() => {
    if (selectedIndex !== null) {
      panelRef.current?.focus();
    }
  }, [selectedIndex]);

  if (selectedIndex === null || citations.length === 0) return null;

  const citation = citations[selectedIndex];

  return (
    <>
      {/* Backdrop (click to close) */}
      <div
        style={styles.backdrop}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="complementary"
        aria-label={`Cita ${selectedIndex + 1}`}
        tabIndex={-1}
        style={styles.panel}
      >
        <div style={styles.header}>
          <h2 style={styles.title}>
            <span style={styles.chip}>[{selectedIndex + 1}]</span>
            Fuente
          </h2>
          <button
            onClick={onClose}
            style={styles.closeBtn}
            aria-label="Cerrar panel de cita"
          >
            ✕
          </button>
        </div>

        <div style={styles.body}>
          {citation.section && (
            <p style={styles.section}>
              <strong>Sección:</strong> {citation.section}
            </p>
          )}
          {citation.source && (
            <p style={styles.source}>
              <strong>Fuente:</strong>{" "}
              <a
                href={citation.source}
                target="_blank"
                rel="noopener noreferrer"
                style={styles.link}
              >
                {citation.source}
              </a>
            </p>
          )}
          {citation.chunk_hash && (
            <p style={styles.meta}>
              <span style={styles.label}>Hash:</span>{" "}
              <code style={styles.hash}>{citation.chunk_hash.slice(0, 12)}…</code>
            </p>
          )}
        </div>

        {/* All citations list */}
        {citations.length > 1 && (
          <div style={styles.allCitations}>
            <p style={styles.allLabel}>Todas las citas</p>
            {citations.map((cit, i) => (
              <button
                key={i}
                style={{
                  ...styles.citItem,
                  ...(i === selectedIndex ? styles.citItemActive : {}),
                }}
                onClick={() => {
                  // Bubble up: parent should update selectedIndex.
                  // For simplicity we use a DOM event; the parent handles it via onCitationClick.
                  // Since CitationsPanel doesn't have direct access to parent's handler,
                  // we dispatch a custom event that ChatPage intercepts.
                  document.dispatchEvent(
                    new CustomEvent("select-citation", { detail: i }),
                  );
                }}
                aria-label={`Cita ${i + 1}: ${cit.section || cit.source}`}
                aria-current={i === selectedIndex ? "true" : undefined}
              >
                <span style={styles.citChip}>[{i + 1}]</span>
                <span style={styles.citText}>{cit.section || cit.source}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

const styles = {
  backdrop: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(0,0,0,0.15)",
    zIndex: 99,
  } as React.CSSProperties,

  panel: {
    position: "fixed" as const,
    top: 0,
    right: 0,
    bottom: 0,
    width: "min(420px, 100vw)",
    background: "var(--bg)",
    borderLeft: "1px solid #dde3e5",
    boxShadow: "-4px 0 20px rgba(0,0,0,0.08)",
    zIndex: 100,
    display: "flex",
    flexDirection: "column" as const,
    outline: "none",
  } as React.CSSProperties,

  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "1rem 1.25rem",
    borderBottom: "1px solid #dde3e5",
    gap: "0.5rem",
  } as React.CSSProperties,

  title: {
    margin: 0,
    fontSize: "1rem",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    color: "var(--fg)",
  } as React.CSSProperties,

  chip: {
    background: "var(--highlight)",
    color: "var(--bg)",
    borderRadius: 4,
    padding: "0 6px",
    fontSize: "0.8em",
    fontFamily: "var(--font-mono)",
    fontWeight: 600,
  } as React.CSSProperties,

  closeBtn: {
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "var(--muted)",
    fontSize: "1.1rem",
    padding: "0.25rem",
    lineHeight: 1,
    borderRadius: 4,
  } as React.CSSProperties,

  body: {
    padding: "1rem 1.25rem",
    overflowY: "auto" as const,
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.6rem",
  } as React.CSSProperties,

  section: {
    margin: 0,
    fontSize: "0.9rem",
    color: "var(--fg)",
    lineHeight: 1.5,
  } as React.CSSProperties,

  source: {
    margin: 0,
    fontSize: "0.9rem",
    color: "var(--fg)",
    wordBreak: "break-all" as const,
  } as React.CSSProperties,

  link: {
    color: "var(--accent)",
    textDecoration: "underline",
  } as React.CSSProperties,

  meta: {
    margin: 0,
    fontSize: "0.85rem",
    color: "var(--muted)",
  } as React.CSSProperties,

  label: {
    fontWeight: 500,
  } as React.CSSProperties,

  hash: {
    fontFamily: "var(--font-mono)",
    fontSize: "0.85em",
    background: "#f0f4f5",
    borderRadius: 3,
    padding: "0.1em 0.3em",
  } as React.CSSProperties,

  allCitations: {
    padding: "0.75rem 1.25rem",
    borderTop: "1px solid #dde3e5",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.3rem",
  } as React.CSSProperties,

  allLabel: {
    margin: "0 0 0.4rem",
    fontSize: "0.8rem",
    fontWeight: 600,
    color: "var(--muted)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  } as React.CSSProperties,

  citItem: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    background: "none",
    border: "1px solid transparent",
    borderRadius: 6,
    padding: "0.35rem 0.5rem",
    cursor: "pointer",
    textAlign: "left" as const,
    width: "100%",
    fontSize: "0.875rem",
    color: "var(--fg)",
    transition: "background 0.1s",
  } as React.CSSProperties,

  citItemActive: {
    background: "#f0f7f5",
    borderColor: "var(--highlight)",
  } as React.CSSProperties,

  citChip: {
    flexShrink: 0,
    background: "var(--highlight)",
    color: "var(--bg)",
    borderRadius: 4,
    padding: "0 5px",
    fontSize: "0.75em",
    fontFamily: "var(--font-mono)",
    fontWeight: 600,
  } as React.CSSProperties,

  citText: {
    overflow: "hidden" as const,
    textOverflow: "ellipsis" as const,
    whiteSpace: "nowrap" as const,
    color: "var(--muted)",
    fontSize: "0.85em",
  } as React.CSSProperties,
};

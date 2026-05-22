/**
 * ChatPage — protected route.
 *
 * Placeholder for the full chat UI (Bloque FE). For now shows the current
 * user's email and a logout button so the auth flow is exercisable end-to-end.
 */
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function ChatPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <main style={styles.page}>
      <header style={styles.header}>
        <h1 style={styles.title}>Chatbot RAG · FastAPI docs</h1>
        <div style={styles.userBar}>
          <span style={styles.email}>{user?.email}</span>
          <button onClick={handleLogout} style={styles.logoutBtn}>
            Cerrar sesión
          </button>
        </div>
      </header>

      <section style={styles.body}>
        <p style={styles.placeholder}>
          La UI de chat llega en el bloque FE. Autenticación operativa ✓
        </p>
      </section>
    </main>
  );
}

const styles = {
  page: {
    fontFamily: "system-ui, sans-serif",
    display: "flex",
    flexDirection: "column" as const,
    height: "100vh",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "1rem 2rem",
    borderBottom: "1px solid #e5e7eb",
    background: "#fff",
  },
  title: { margin: 0, fontSize: "1.2rem", fontWeight: 600 },
  userBar: { display: "flex", alignItems: "center", gap: "1rem" },
  email: { fontSize: "0.875rem", color: "#6b7280" },
  logoutBtn: {
    padding: "0.35rem 0.75rem",
    background: "transparent",
    border: "1px solid #d1d5db",
    borderRadius: 4,
    cursor: "pointer",
    fontSize: "0.875rem",
  },
  body: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f9fafb",
  },
  placeholder: { color: "#6b7280" },
};

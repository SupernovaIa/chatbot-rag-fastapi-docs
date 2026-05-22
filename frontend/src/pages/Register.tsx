/**
 * Register page — POST /auth/register then auto-login.
 * Redirects to / on success.
 */
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("Las contraseñas no coinciden");
      return;
    }
    setSubmitting(true);
    try {
      await register(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al registrarse");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Crear cuenta</h1>

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={styles.input}
            />
          </label>

          <label style={styles.label}>
            Contraseña
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
              style={styles.input}
            />
          </label>

          <label style={styles.label}>
            Confirmar contraseña
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
              style={styles.input}
            />
          </label>

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" disabled={submitting} style={styles.button}>
            {submitting ? "Creando cuenta…" : "Crear cuenta"}
          </button>
        </form>

        <p style={styles.footer}>
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" style={styles.link}>
            Inicia sesión
          </Link>
        </p>
      </div>
    </main>
  );
}

const styles = {
  page: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "100vh",
    background: "#f5f5f5",
    fontFamily: "system-ui, sans-serif",
  } as React.CSSProperties,
  card: {
    background: "#fff",
    borderRadius: 8,
    boxShadow: "0 2px 8px rgba(0,0,0,.1)",
    padding: "2rem",
    width: "100%",
    maxWidth: 360,
  } as React.CSSProperties,
  title: { margin: "0 0 1.5rem", fontSize: "1.4rem" } as React.CSSProperties,
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "1rem",
  } as React.CSSProperties,
  label: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.25rem",
    fontSize: "0.9rem",
  } as React.CSSProperties,
  input: {
    padding: "0.5rem 0.75rem",
    borderRadius: 4,
    border: "1px solid #ccc",
    fontSize: "1rem",
  } as React.CSSProperties,
  error: {
    color: "#c0392b",
    margin: 0,
    fontSize: "0.875rem",
  } as React.CSSProperties,
  button: {
    padding: "0.6rem",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    fontSize: "1rem",
    cursor: "pointer",
  } as React.CSSProperties,
  footer: { marginTop: "1rem", fontSize: "0.875rem", textAlign: "center" as const },
  link: { color: "#2563eb" },
};

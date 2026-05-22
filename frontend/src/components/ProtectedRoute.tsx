/**
 * Wraps a route so only authenticated users can access it.
 * Redirects to /login while the auth state is loading or when the user is null.
 */
import { Navigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

interface Props {
  children: React.ReactNode;
}

export default function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
        <p>Cargando…</p>
      </main>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

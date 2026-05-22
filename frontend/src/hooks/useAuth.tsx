/**
 * Auth context + hook.
 *
 * Provides the current user (null if not logged in) and login/logout/register
 * helpers. Fetches /auth/me on mount to rehydrate session from cookie.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import * as authApi from "../api/auth";
import type { UserOut } from "../api/auth";

interface AuthState {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);

  // Rehydrate from cookie on mount
  useEffect(() => {
    authApi
      .getMe()
      .then(setUser)
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await authApi.login(email, password);
    const me = await authApi.getMe();
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    await authApi.register(email, password);
    // Auto-login after register
    await authApi.login(email, password);
    const me = await authApi.getMe();
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    await authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Returns the auth context. Must be used inside <AuthProvider>. */
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

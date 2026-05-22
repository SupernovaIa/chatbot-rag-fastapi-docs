/**
 * Auth API calls against the FastAPI Users backend.
 *
 * Login uses OAuth2 PasswordRequestForm (form-encoded, field name "username").
 * Register and me use JSON.
 * All requests include credentials so the httpOnly cookie is sent/set.
 */

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface UserOut {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}

async function _assertOk(res: Response): Promise<void> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const msg = body?.detail ?? `HTTP ${res.status}`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
}

/** POST /auth/register — creates a new account. */
export async function register(email: string, password: string): Promise<UserOut> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  await _assertOk(res);
  return res.json();
}

/**
 * POST /auth/login — OAuth2 PasswordRequestForm (form-encoded).
 * Sets the `access_token` httpOnly cookie on success.
 */
export async function login(email: string, password: string): Promise<void> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  await _assertOk(res);
}

/** POST /auth/logout — clears the access_token cookie. */
export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

/** GET /auth/me — returns current user or null if not authenticated. */
export async function getMe(): Promise<UserOut | null> {
  const res = await fetch(`${BASE}/auth/me`, {
    credentials: "include",
  });
  if (res.status === 401) return null;
  if (!res.ok) return null;
  return res.json();
}

import type { AssetStatusResponse, SimilarityResultResponse } from "@/types";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "overwatch_auth_token";

export type ApiResult<T> =
  | { ok: true;  data: T }
  | { ok: false; error: string };

// ─── Token Management ────────────────────────────────────────────────────────
export const auth = {
  setToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  getToken: () => localStorage.getItem(TOKEN_KEY),
  clearToken: () => localStorage.removeItem(TOKEN_KEY),
};

function handleUnauthorized() {
  auth.clearToken();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// ─── Protected Fetch Wrapper ─────────────────────────────────────────────────
/** Never throws — returns ok:false on any error */
export async function apiFetch<T = unknown>(
  path:    string,
  options?: RequestInit,
): Promise<ApiResult<T>> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    const token = auth.getToken();
    const headers = new Headers(options?.headers);
    
    // Default to JSON unless explicitly overridden
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    // Inject JWT if session exists
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), 20000);
    const signal = options?.signal ?? controller.signal;

    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers,
      signal,
    });

    // Auto-logout on token expiration
    if (res.status === 401) {
      handleUnauthorized();
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      return { ok: false, error: errData?.detail || `HTTP ${res.status}` };
    }
    
    const data: T = await res.json();
    return { ok: true, data };
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      return { ok: false, error: "Request timed out. Please try again." };
    }
    return { ok: false, error: String(e) };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

// ─── Protected Upload Wrapper ────────────────────────────────────────────────
/** Multipart upload — never throws */
export async function apiUpload(
  path:    string,
  file:    File,
): Promise<ApiResult<Record<string, unknown>>> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    const token = auth.getToken();
    const form = new FormData();
    form.append("file", file);

    const headers = new Headers();
    // Inject JWT. Notice we removed X-User-Role — the backend gets it from the token now!
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), 30000);

    const res = await fetch(`${BASE}${path}`, {
      method:  "POST",
      headers, // Browser automatically sets the Content-Type with the multipart boundary
      body:    form,
      signal: controller.signal,
    });

    if (res.status === 401) {
      handleUnauthorized();
    }

    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      return { ok: false, error: errData?.detail || `HTTP ${res.status}` };
    }
    
    const data = await res.json();
    return { ok: true, data };
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      return { ok: false, error: "Upload timed out. Please try again." };
    }
    return { ok: false, error: String(e) };
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

// ─── Auth API Calls ──────────────────────────────────────────────────────────
export const authApi = {
  requestOtp: async (
    email: string,
    role: string,
    mode: "LOGIN" | "SIGNUP",
    name?: string,
  ) => {
    return apiFetch<{ message: string }>("/api/v1/auth/request-otp", {
      method: "POST",
      body: JSON.stringify({ email, role, mode, name }),
    });
  },

  verifyOtp: async (email: string, code: string) => {
    const result = await apiFetch<{ access_token: string; role: string; name: string }>("/api/v1/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, code: String(code) }),
    });
    
    // Save the VIP wristband immediately upon success
    if (result.ok && result.data.access_token) {
      auth.setToken(result.data.access_token);
    }
    return result;
  },

  googleAuth: async (
    credential: string,
    mode: "LOGIN" | "SIGNUP",
    role: string,
  ) => {
    const result = await apiFetch<{ access_token: string; role: string; name: string }>("/api/v1/auth/google", {
      method: "POST",
      body: JSON.stringify({ credential, mode, role }),
    });

    if (result.ok && result.data.access_token) {
      auth.setToken(result.data.access_token);
    }
    return result;
  },

  me: async () => {
    return apiFetch<{ sub: string; name: string; role: string }>("/api/v1/auth/me", {
      method: "GET",
    });
  },
};

export const assetApi = {
  status: (assetId: string) =>
    apiFetch<AssetStatusResponse>(`/api/v1/assets/${assetId}/status`, {
      method: "GET",
    }),

  result: (assetId: string) =>
    apiFetch<SimilarityResultResponse>(`/api/v1/assets/${assetId}/result`, {
      method: "GET",
    }),
};

// ─── Types ───────────────────────────────────────────────────────────────────
export type HealthResponse = {
  status:  string;
  version: string;
};

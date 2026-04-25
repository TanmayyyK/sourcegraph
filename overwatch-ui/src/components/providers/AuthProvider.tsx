import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { auth, authApi } from "@/lib/api";

type AuthUser = {
  email: string;
  name: string;
  role: string;
  exp?: number;
};

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoading: boolean;
  userName: string;
  userRole: string;
  userEmail: string;
  refreshSession: () => Promise<boolean>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwt(token: string): AuthUser | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payloadBase64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payloadJson = decodeURIComponent(
      atob(payloadBase64)
        .split("")
        .map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, "0")}`)
        .join(""),
    );
    const payload = JSON.parse(payloadJson) as {
      sub?: string;
      name?: string;
      role?: string;
      exp?: number;
    };
    if (!payload.sub || !payload.name || !payload.role) return null;
    if (payload.exp && Date.now() >= payload.exp * 1000) return null;
    return {
      email: payload.sub,
      name: payload.name,
      role: payload.role,
      exp: payload.exp,
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = async (): Promise<boolean> => {
    const token = auth.getToken();
    if (!token) {
      setUser(null);
      return false;
    }

    const decoded = decodeJwt(token);
    if (!decoded) {
      auth.clearToken();
      setUser(null);
      return false;
    }

    const me = await authApi.me();
    if (!me.ok) {
      auth.clearToken();
      setUser(null);
      return false;
    }

    setUser({
      email: me.data.sub,
      name: me.data.name,
      role: me.data.role,
      exp: decoded.exp,
    });
    return true;
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        await refreshSession();
      } finally {
        setIsLoading(false);
      }
    };
    void bootstrap();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: Boolean(user),
      isLoading,
      userName: user?.name ?? "",
      userRole: user?.role ?? "",
      userEmail: user?.email ?? "",
      refreshSession,
      logout: () => {
        auth.clearToken();
        setUser(null);
      },
    }),
    [isLoading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}

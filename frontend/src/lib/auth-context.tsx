/**
 * SafeVision AI — Auth Context
 *
 * Provides authentication state management across the app.
 * - On mount: validates existing token via GET /api/users/me
 * - login(): stores token in localStorage (remember) or sessionStorage
 * - logout(): clears both storages defensively
 * - Token is never exposed in rendered UI
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { UserResponse } from "./api-types";
import { clearAuthToken, fetchMe, getAuthToken, loginApi, setAuthToken } from "./api-client";

interface AuthContextValue {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount — check for existing token and validate it
  useEffect(() => {
    const existingToken = getAuthToken();
    if (!existingToken) {
      setIsLoading(false);
      return;
    }

    setToken(existingToken);

    fetchMe()
      .then((userData) => {
        setUser(userData);
        setToken(existingToken);
      })
      .catch(() => {
        // Token is invalid or expired — clear it
        clearAuthToken();
        setToken(null);
        setUser(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const response = await loginApi(email, password);
    setAuthToken(response.access_token, remember);
    setToken(response.access_token);
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    setToken(null);
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: !!user && !!token,
      isLoading,
      login,
      logout,
    }),
    [user, token, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

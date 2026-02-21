"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, type User } from "./api";

type AuthContextType = {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => void;
  loading: boolean;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
  refreshUser: () => {},
  loading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem("angie_token");
    if (stored) {
      setToken(stored);
      api.users
        .me(stored)
        .then(setUser)
        .catch(() => {
          localStorage.removeItem("angie_token");
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await api.auth.login(username, password);
    if (!tokens.access_token) throw new Error("Login failed");
    localStorage.setItem("angie_token", tokens.access_token);
    setToken(tokens.access_token);
    const me = await api.users.me(tokens.access_token);
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("angie_token");
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(() => {
    if (token) {
      api.users.me(token).then(setUser).catch(() => {});
    }
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, login, logout, refreshUser, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

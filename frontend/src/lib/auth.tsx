"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "./api";
import type { User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (e: string, p: string) => Promise<void>;
  register: (e: string, p: string, n?: string) => Promise<void>;
  completeLogin: (access: string, refresh: string) => Promise<void>;
  logout: () => void;
  logoutAll: () => Promise<void>;
}

const Ctx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const t = localStorage.getItem("access_token");
    if (!t) {
      const id = setTimeout(() => setLoading(false), 0);
      return () => clearTimeout(id);
    }
    authApi.me().then((r) => setUser(r.data)).catch(() => { localStorage.removeItem("access_token"); localStorage.removeItem("refresh_token"); }).finally(() => setLoading(false));
  }, []);
  const login = async (email: string, password: string) => {
    const r = await authApi.login(email, password);
    if (r.data.mfa_required) {
      sessionStorage.setItem("mfa_token", r.data.mfa_token ?? "");
      router.push("/mfa");
      return;
    }
    if (!r.data.access_token || !r.data.refresh_token) throw new Error("Login returned no tokens");
    localStorage.setItem("access_token", r.data.access_token);
    localStorage.setItem("refresh_token", r.data.refresh_token);
    const me = await authApi.me();
    setUser(me.data);
  };
  const register = async (email: string, password: string, full_name?: string) => {
    const r = await authApi.register(email, password, full_name);
    localStorage.setItem("access_token", r.data.access_token);
    localStorage.setItem("refresh_token", r.data.refresh_token);
    const me = await authApi.me();
    setUser(me.data);
  };
  const completeLogin = async (access: string, refresh: string) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    const me = await authApi.me();
    setUser(me.data);
  };
  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    router.push("/login");
  };
  const logoutAll = async () => {
    // Revokes every token server-side, then signs this device out too.
    try { await authApi.logoutAll(); } catch {}
    logout();
  };
  return <Ctx.Provider value={{ user, loading, login, register, completeLogin, logout, logoutAll }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("no auth");
  return c;
}
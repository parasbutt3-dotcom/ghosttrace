import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const { authApi } = vi.hoisted(() => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logoutAll: vi.fn(),
    mfaLogin: vi.fn(),
  },
}));
vi.mock("@/lib/api", () => ({ authApi }));

import { AuthProvider, useAuth } from "./auth";

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("AuthContext token handling", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("starts unauthenticated when no access token is stored", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toBeNull();
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it("loads user from /me when an access token exists", async () => {
    localStorage.setItem("access_token", "tok");
    authApi.me.mockResolvedValue({ data: { id: "1", email: "a@b.com", is_admin: false } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(authApi.me).toHaveBeenCalled();
    expect(result.current.user?.email).toBe("a@b.com");
  });

  it("clears tokens when /me fails on bootstrap", async () => {
    localStorage.setItem("access_token", "tok");
    localStorage.setItem("refresh_token", "rt");
    authApi.me.mockRejectedValue(new Error("401"));
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(result.current.user).toBeNull();
  });

  it("logout removes tokens and user", async () => {
    localStorage.setItem("access_token", "tok");
    localStorage.setItem("refresh_token", "rt");
    authApi.me.mockResolvedValue({ data: { id: "1", email: "a@b.com", is_admin: false } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.user).not.toBeNull());
    act(() => result.current.logout());
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(result.current.user).toBeNull();
    expect(push).toHaveBeenCalledWith("/login");
  });
});

describe("AuthContext login MFA-required flow", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("stores mfa_token and redirects to /mfa without persisting auth tokens", async () => {
    authApi.login.mockResolvedValue({ data: { mfa_required: true, mfa_token: "mtok" } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login("u@x.com", "pw");
    });
    expect(authApi.login).toHaveBeenCalledWith("u@x.com", "pw");
    expect(sessionStorage.getItem("mfa_token")).toBe("mtok");
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(push).toHaveBeenCalledWith("/mfa");
    expect(authApi.me).not.toHaveBeenCalled();
  });

  it("persists tokens and loads user on normal login", async () => {
    authApi.login.mockResolvedValue({ data: { mfa_required: false, access_token: "a", refresh_token: "r" } });
    authApi.me.mockResolvedValue({ data: { id: "2", email: "u@x.com", is_admin: false } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.login("u@x.com", "pw");
    });
    expect(localStorage.getItem("access_token")).toBe("a");
    expect(localStorage.getItem("refresh_token")).toBe("r");
    expect(result.current.user?.email).toBe("u@x.com");
  });

  it("completeLogin persists tokens and loads user", async () => {
    authApi.me.mockResolvedValue({ data: { id: "3", email: "c@x.com", is_admin: false } });
    const { result } = renderHook(() => useAuth(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.completeLogin("A", "R");
    });
    expect(localStorage.getItem("access_token")).toBe("A");
    expect(localStorage.getItem("refresh_token")).toBe("R");
    expect(result.current.user?.email).toBe("c@x.com");
  });
});
import { describe, it, expect, vi, beforeEach } from "vitest";

interface RetryConfig {
  _retry?: boolean;
  headers?: Record<string, string>;
}

const { mockInstance, mockPost, handlers } = vi.hoisted(() => {
  const handlers = {
    req: [] as Array<(cfg: RetryConfig) => RetryConfig>,
    res: [] as Array<{ err: (e: unknown) => Promise<unknown> }>,
  };
  const instance = vi.fn();
  const post = vi.fn();
  const create = vi.fn(() => instance);
  (instance as unknown as { interceptors: unknown }).interceptors = {
    request: { use: (fn: (cfg: RetryConfig) => RetryConfig) => { handlers.req.push(fn); } },
    response: { use: (_ok: unknown, err: (e: unknown) => Promise<unknown>) => { handlers.res.push({ err }); } },
  };
  return { mockInstance: instance, mockPost: post, handlers, create };
});

vi.mock("axios", () => {
  const create = vi.fn(() => mockInstance);
  return { default: { create, post: mockPost }, create, post: mockPost };
});

import "@/lib/api";

describe("api.ts refresh interceptor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    handlers.req.length = 0;
    handlers.res.length = 0;
    localStorage.clear();
    vi.resetModules();
  });

  async function load() {
    await import("@/lib/api");
  }

  it("request interceptor attaches Bearer token from localStorage", async () => {
    await load();
    localStorage.setItem("access_token", "access123");
    const cfg: RetryConfig = { headers: {} };
    const out = handlers.req[0](cfg);
    expect(out.headers?.Authorization).toBe("Bearer access123");
  });

  it("retries the original request after a successful refresh on 401", async () => {
    await load();
    localStorage.setItem("refresh_token", "rtok");
    mockPost.mockResolvedValue({ data: { access_token: "newAccess", refresh_token: "newRefresh" } });
    mockInstance.mockResolvedValue({ data: "retried-ok" });

    const original: RetryConfig = { _retry: false, headers: {} };
    const err = { response: { status: 401 }, config: original };

    const res = await handlers.res[0].err(err);

    expect(mockPost).toHaveBeenCalled();
    expect(localStorage.getItem("access_token")).toBe("newAccess");
    expect(localStorage.getItem("refresh_token")).toBe("newRefresh");
    expect(original.headers?.Authorization).toBe("Bearer newAccess");
    expect(mockInstance).toHaveBeenCalledWith(original);
    expect(res).toEqual({ data: "retried-ok" });
  });

  it("does not retry when there is no refresh token", async () => {
    await load();
    const original: RetryConfig = { _retry: false, headers: {} };
    const err = { response: { status: 401 }, config: original };

    await expect(handlers.res[0].err(err)).rejects.toBe(err);
    expect(mockPost).not.toHaveBeenCalled();
  });

  it("clears tokens and rejects when refresh fails", async () => {
    await load();
    localStorage.setItem("access_token", "a");
    localStorage.setItem("refresh_token", "r");
    mockPost.mockRejectedValue(new Error("refresh failed"));

    const original: RetryConfig = { _retry: false, headers: {} };
    const err = { response: { status: 401 }, config: original };

    await expect(handlers.res[0].err(err)).rejects.toBe(err);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("does not retry non-401 errors", async () => {
    await load();
    const original: RetryConfig = { _retry: false, headers: {} };
    const err = { response: { status: 500 }, config: original };
    await expect(handlers.res[0].err(err)).rejects.toBe(err);
    expect(mockPost).not.toHaveBeenCalled();
  });
});
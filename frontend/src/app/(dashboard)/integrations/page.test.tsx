import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";

const { integrationsApi, takeoutApi } = vi.hoisted(() => ({
  integrationsApi: {
    list: vi.fn(),
    accounts: vi.fn(),
    kinds: vi.fn(),
    create: vi.fn(),
    get: vi.fn(),
    summary: vi.fn(),
    sync: vi.fn(),
    delete: vi.fn(),
    disconnectAccount: vi.fn(),
    googleLogin: vi.fn(),
  },
  takeoutApi: { import: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ integrationsApi, takeoutApi, errDetail: (x: unknown, f: string) => f }));

import IntegrationsPage from "./page";

describe("IntegrationsPage render with mocked api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    integrationsApi.list.mockResolvedValue({ data: [] });
    integrationsApi.accounts.mockResolvedValue({ data: [] });
    integrationsApi.kinds.mockResolvedValue({ data: { kinds: ["activitywatch", "github"] } });
  });

  it("renders the page heading", async () => {
    render(<IntegrationsPage />);
    expect(screen.getByText("Integrations")).toBeInTheDocument();
    await waitFor(() => expect(integrationsApi.list).toHaveBeenCalled());
  });

  it("shows empty state for connected accounts", async () => {
    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.getByText("No connected accounts.")).toBeInTheDocument());
  });

  it("renders integrations returned by the api", async () => {
    integrationsApi.list.mockResolvedValue({
      data: [
        { id: "i1", kind: "github", name: "My GitHub", enabled: true, status: "ok", last_sync_at: null, last_error: null, created_at: "2026-01-01" },
      ],
    });
    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.getByText("My GitHub")).toBeInTheDocument());
    expect(screen.getByText(/github · ok/)).toBeInTheDocument();
  });

  it("renders available kinds in the add form", async () => {
    render(<IntegrationsPage />);
    await waitFor(() => expect(screen.getByRole("option", { name: "github" })).toBeInTheDocument());
  });
});
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";

const { eventsApi } = vi.hoisted(() => ({
  eventsApi: { list: vi.fn(), stats: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ eventsApi }));
vi.mock("next/dynamic", () => ({ default: () => () => null }));

import TimelinePage from "./page";

describe("TimelinePage filter state", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    eventsApi.list.mockResolvedValue({ data: { total: 0, items: [], offset: 0, limit: 200, next_offset: null } });
  });

  it("renders the timeline heading", async () => {
    render(<TimelinePage />);
    expect(screen.getByText("Activity Timeline")).toBeInTheDocument();
    await waitFor(() => expect(eventsApi.list).toHaveBeenCalled());
  });

  it("shows a filter chip after entering a source and clears it on click", async () => {
    const user = userEvent.setup();
    render(<TimelinePage />);
    const sourceInput = screen.getByPlaceholderText("Source");
    await user.type(sourceInput, "github");
    expect(screen.getByText("source: github ✕")).toBeInTheDocument();
    await user.click(screen.getByText("source: github ✕"));
    expect(screen.queryByText("source: github ✕")).not.toBeInTheDocument();
  });

  it("shows a search chip and clears search", async () => {
    const user = userEvent.setup();
    render(<TimelinePage />);
    const searchInput = screen.getByPlaceholderText("Search…");
    await user.type(searchInput, "login");
    expect(screen.getByText("search: login ✕")).toBeInTheDocument();
    await user.click(screen.getByText("search: login ✕"));
    expect(screen.queryByText("search: login ✕")).not.toBeInTheDocument();
  });

  it("calls eventsApi.list with filter params", async () => {
    const user = userEvent.setup();
    render(<TimelinePage />);
    await waitFor(() => expect(eventsApi.list).toHaveBeenCalled());
    const sourceInput = screen.getByPlaceholderText("Source");
    await user.type(sourceInput, "github");
    await user.click(screen.getByText("Filter"));
    await waitFor(() => {
      const lastCall = eventsApi.list.mock.calls[eventsApi.list.mock.calls.length - 1][0];
      expect(lastCall.source).toBe("github");
    });
  });
});
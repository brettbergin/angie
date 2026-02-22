import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SchedulesPage from "../page";

const mockSchedules = [
  {
    id: "s1",
    user_id: "u1",
    name: "Nightly Backup",
    description: "Backup all DBs",
    cron_expression: "0 0 * * *",
    cron_human: "Every day at 0:00 UTC",
    agent_slug: null,
    task_payload: {},
    is_enabled: true,
    last_run_at: null,
    next_run_at: "2025-01-02T00:00:00Z",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    id: "s2",
    user_id: "u1",
    name: "Weekly Report",
    description: null,
    cron_expression: "0 9 * * 1",
    cron_human: "Every Monday at 9:00 UTC",
    agent_slug: "github",
    task_payload: {},
    is_enabled: false,
    last_run_at: null,
    next_run_at: null,
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
];

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    token: "test-token",
    user: { id: "u1" },
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    loading: false,
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/schedules",
}));

const mockList = vi.fn();
const mockToggle = vi.fn();
const mockDelete = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    schedules: {
      list: (...args: unknown[]) => mockList(...args),
      toggle: (...args: unknown[]) => mockToggle(...args),
      delete: (...args: unknown[]) => mockDelete(...args),
      create: vi.fn(),
      update: vi.fn(),
    },
  },
}));

describe("SchedulesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue(mockSchedules);
    mockToggle.mockResolvedValue({ ...mockSchedules[0], is_enabled: false });
    mockDelete.mockResolvedValue(undefined);
  });

  it("renders schedule list", async () => {
    render(<SchedulesPage />);
    await waitFor(() => {
      expect(screen.getByText("Nightly Backup")).toBeTruthy();
      expect(screen.getByText("Weekly Report")).toBeTruthy();
    });
    expect(screen.getByText("Every day at 0:00 UTC")).toBeTruthy();
  });

  it("shows empty state when no schedules", async () => {
    mockList.mockResolvedValue([]);
    render(<SchedulesPage />);
    await waitFor(() => {
      expect(screen.getByText(/No schedules yet/)).toBeTruthy();
    });
  });

  it("opens create form when clicking New Schedule", async () => {
    render(<SchedulesPage />);
    await waitFor(() =>
      expect(screen.getByText("Nightly Backup")).toBeTruthy()
    );
    fireEvent.click(screen.getByText("New Schedule"));
    expect(screen.getByText("Create Schedule")).toBeTruthy();
  });

  it("filters schedules by search", async () => {
    render(<SchedulesPage />);
    await waitFor(() =>
      expect(screen.getByText("Nightly Backup")).toBeTruthy()
    );
    const search = screen.getByPlaceholderText("Search schedules…");
    fireEvent.change(search, { target: { value: "Weekly" } });
    expect(screen.queryByText("Nightly Backup")).toBeNull();
    expect(screen.getByText("Weekly Report")).toBeTruthy();
  });
});

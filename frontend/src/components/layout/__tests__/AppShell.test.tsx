import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// We need to mock auth before importing AppShell
const mockUseAuth = vi.fn();
vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => mockUseAuth(),
}));

// Mock Sidebar
vi.mock("@/components/layout/Sidebar", () => ({
  Sidebar: () => <nav data-testid="sidebar">Sidebar</nav>,
}));

// Mock Spinner
vi.mock("@/components/ui/spinner", () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: mockReplace, back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// Import after mocks
import { AppShell } from "../AppShell";

describe("AppShell", () => {
  it("shows spinner while auth is loading", () => {
    mockUseAuth.mockReturnValue({
      user: null,
      token: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      loading: true,
    });

    render(<AppShell><div>Content</div></AppShell>);
    expect(screen.getByTestId("spinner")).toBeInTheDocument();
  });

  it("redirects to /login when no user after loading", async () => {
    mockUseAuth.mockReturnValue({
      user: null,
      token: null,
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      loading: false,
    });

    render(<AppShell><div>Content</div></AppShell>);
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
  });

  it("renders children when user is authenticated", () => {
    mockUseAuth.mockReturnValue({
      user: { id: "1", username: "alice" },
      token: "tok",
      login: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
      loading: false,
    });

    render(<AppShell><div>Protected Content</div></AppShell>);
    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });
});

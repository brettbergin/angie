import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Sidebar } from "../Sidebar";

const mockLogout = vi.fn();
const mockUser = { id: "1", email: "a@b.com", username: "alice", full_name: null, timezone: "UTC", is_active: true };

// Mock useAuth
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    token: "tok",
    login: vi.fn(),
    logout: mockLogout,
    refreshUser: vi.fn(),
    loading: false,
  }),
}));

// Mock usePathname to return /chat
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/chat",
}));

describe("Sidebar", () => {
  it("renders all 9 navigation items with correct hrefs and section headers", () => {
    render(<Sidebar />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((l) => l.getAttribute("href"));
    expect(hrefs).toContain("/dashboard");
    expect(hrefs).toContain("/chat");
    expect(hrefs).toContain("/agents");
    expect(hrefs).toContain("/teams");
    expect(hrefs).toContain("/events");
    expect(hrefs).toContain("/tasks");
    expect(hrefs).toContain("/workflows");
    expect(hrefs).toContain("/connections");
    expect(hrefs).toContain("/settings");

    expect(screen.getByText("Main")).toBeTruthy();
    expect(screen.getByText("Work")).toBeTruthy();
    expect(screen.getByText("Configure")).toBeTruthy();
  });

  it("active route item has highlighted class", () => {
    render(<Sidebar />);
    const chatLink = screen.getByRole("link", { name: /chat/i });
    expect(chatLink.className).toContain("bg-angie-600/20");
  });

  it("user avatar shows first letter of username", () => {
    render(<Sidebar />);
    // The user section avatar (inside the border-t section)
    const userSection = screen.getByText("alice").closest("div.flex.items-center")!;
    const avatar = userSection.querySelector(".rounded-full")!;
    expect(avatar.textContent).toBe("A");
  });

  it("logout button calls logout()", () => {
    render(<Sidebar />);
    const logoutBtn = screen.getByTitle("Sign out");
    fireEvent.click(logoutBtn);
    expect(mockLogout).toHaveBeenCalledOnce();
  });
});

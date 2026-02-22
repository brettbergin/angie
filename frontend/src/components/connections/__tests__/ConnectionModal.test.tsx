import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ConnectionModal } from "../ConnectionModal";
import type { ServiceDefinition, Connection } from "@/lib/api";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ token: "tok", user: null, login: vi.fn(), logout: vi.fn(), refreshUser: vi.fn(), loading: false }),
}));

const mockService: ServiceDefinition = {
  key: "github",
  name: "GitHub",
  description: "GitHub integration",
  auth_type: "api_key",
  color: "#333333",
  fields: [{ key: "personal_access_token", label: "Personal Access Token", type: "password" }],
  agent_slug: "github",
};

const mockConnection: Connection = {
  id: "conn-1",
  service_type: "github",
  display_name: "GitHub",
  auth_type: "api_key",
  status: "connected",
  masked_credentials: { personal_access_token: "ghp_****xyz" },
  scopes: null,
  token_expires_at: null,
  last_used_at: null,
  last_tested_at: "2024-01-01T00:00:00",
  created_at: "2024-01-01T00:00:00",
  updated_at: "2024-01-01T00:00:00",
};

describe("ConnectionModal", () => {
  const onClose = vi.fn();
  const onSaved = vi.fn();

  beforeEach(() => {
    onClose.mockClear();
    onSaved.mockClear();
  });

  it("renders service name and description", () => {
    render(<ConnectionModal service={mockService} connection={null} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("GitHub")).toBeTruthy();
    expect(screen.getByText("GitHub integration")).toBeTruthy();
  });

  it("shows Connect button for new connection", () => {
    render(<ConnectionModal service={mockService} connection={null} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("Connect")).toBeTruthy();
  });

  it("shows Update button for existing connection", () => {
    render(<ConnectionModal service={mockService} connection={mockConnection} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("Update")).toBeTruthy();
  });

  it("shows masked credentials for existing connection", () => {
    render(<ConnectionModal service={mockService} connection={mockConnection} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("ghp_****xyz")).toBeTruthy();
  });

  it("shows status indicator for connected state", () => {
    render(<ConnectionModal service={mockService} connection={mockConnection} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("connected")).toBeTruthy();
  });

  it("shows test and disconnect buttons for existing connection", () => {
    render(<ConnectionModal service={mockService} connection={mockConnection} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("Test Connection")).toBeTruthy();
    expect(screen.getByText("Disconnect")).toBeTruthy();
  });

  it("closes on cancel", () => {
    render(<ConnectionModal service={mockService} connection={null} onClose={onClose} onSaved={onSaved} />);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders credential fields from service definition", () => {
    render(<ConnectionModal service={mockService} connection={null} onClose={onClose} onSaved={onSaved} />);
    expect(screen.getByText("Personal Access Token")).toBeTruthy();
  });
});

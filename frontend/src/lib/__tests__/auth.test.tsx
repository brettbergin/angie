import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "../auth";

// Mock the api module
vi.mock("../api", () => ({
  api: {
    auth: {
      login: vi.fn(),
    },
    users: {
      me: vi.fn(),
    },
  },
}));

import { api } from "../api";

const mockedApi = vi.mocked(api);

// Helper component to access auth context
function AuthConsumer({ onAuth }: { onAuth: (auth: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  onAuth(auth);
  return null;
}

function renderWithAuth(onAuth: (auth: ReturnType<typeof useAuth>) => void) {
  return render(
    <AuthProvider>
      <AuthConsumer onAuth={onAuth} />
    </AuthProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("AuthProvider", () => {
  it("reads angie_token from localStorage on mount", async () => {
    localStorage.setItem("angie_token", "stored-token");
    mockedApi.users.me.mockResolvedValue({
      id: "1",
      email: "a@b.com",
      username: "alice",
      full_name: null,
      timezone: "UTC",
      is_active: true,
    });

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));
    expect(mockedApi.users.me).toHaveBeenCalledWith("stored-token");
    expect(auth.token).toBe("stored-token");
    expect(auth.user?.username).toBe("alice");
  });

  it("sets user on mount with valid token", async () => {
    localStorage.setItem("angie_token", "valid");
    mockedApi.users.me.mockResolvedValue({
      id: "1",
      email: "a@b.com",
      username: "bob",
      full_name: "Bob",
      timezone: "UTC",
      is_active: true,
    });

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.user?.username).toBe("bob"));
  });

  it("clears localStorage and resets state on invalid token", async () => {
    localStorage.setItem("angie_token", "expired");
    mockedApi.users.me.mockRejectedValue(new Error("Unauthorized"));

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));
    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(localStorage.getItem("angie_token")).toBeNull();
  });

  it("login() stores token, fetches user profile", async () => {
    mockedApi.auth.login.mockResolvedValue({
      access_token: "new-token",
      refresh_token: "ref",
      token_type: "bearer",
    });
    mockedApi.users.me.mockResolvedValue({
      id: "2",
      email: "c@d.com",
      username: "carol",
      full_name: null,
      timezone: "UTC",
      is_active: true,
    });

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));

    await act(async () => {
      await auth.login("carol", "pass");
    });

    expect(localStorage.getItem("angie_token")).toBe("new-token");
    expect(auth.user?.username).toBe("carol");
  });

  it("login() throws on failed login (no access_token)", async () => {
    mockedApi.auth.login.mockResolvedValue({
      access_token: "",
      refresh_token: "",
      token_type: "",
    });

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));

    await expect(
      act(async () => {
        await auth.login("bad", "creds");
      }),
    ).rejects.toThrow("Login failed");
  });

  it("logout() clears token, user, and localStorage", async () => {
    localStorage.setItem("angie_token", "tok");
    mockedApi.users.me.mockResolvedValue({
      id: "1",
      email: "a@b.com",
      username: "alice",
      full_name: null,
      timezone: "UTC",
      is_active: true,
    });

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.user).not.toBeNull());

    act(() => { auth.logout(); });

    expect(auth.token).toBeNull();
    expect(auth.user).toBeNull();
    expect(localStorage.getItem("angie_token")).toBeNull();
  });

  it("refreshUser() calls api.users.me() when token exists", async () => {
    localStorage.setItem("angie_token", "tok");
    const user = {
      id: "1",
      email: "a@b.com",
      username: "alice",
      full_name: null,
      timezone: "UTC",
      is_active: true,
    };
    mockedApi.users.me.mockResolvedValue(user);

    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));
    mockedApi.users.me.mockClear();

    act(() => { auth.refreshUser(); });

    expect(mockedApi.users.me).toHaveBeenCalledWith("tok");
  });

  it("refreshUser() is a no-op when no token", async () => {
    let auth!: ReturnType<typeof useAuth>;
    renderWithAuth((a) => { auth = a; });

    await waitFor(() => expect(auth.loading).toBe(false));

    act(() => { auth.refreshUser(); });

    expect(mockedApi.users.me).not.toHaveBeenCalled();
  });
});

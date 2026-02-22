import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "../api";

const API_URL = "http://localhost:8000";

beforeEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(body: unknown, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(body),
  } as Response);
}

describe("request() — via api.users.me()", () => {
  it("adds Content-Type: application/json header", async () => {
    const spy = mockFetch({ id: "1", username: "alice" });
    await api.users.me("tok");
    expect(spy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      })
    );
  });

  it("adds Authorization: Bearer header when token provided", async () => {
    const spy = mockFetch({ id: "1" });
    await api.users.me("my-token");
    expect(spy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer my-token" }),
      })
    );
  });

  it("omits Authorization header when no token", async () => {
    const spy = mockFetch([]);
    await api.agents.list(undefined as unknown as string);
    const headers = spy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("returns parsed JSON on success", async () => {
    mockFetch({ id: "1", username: "alice" });
    const user = await api.users.me("tok");
    expect(user).toEqual({ id: "1", username: "alice" });
  });

  it("returns undefined on 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error("no body")),
    } as Response);
    const result = await api.teams.delete("tok", "123");
    expect(result).toBeUndefined();
  });

  it("throws Error with message from API on non-ok response", async () => {
    mockFetch({ detail: "Not found" }, 404);
    await expect(api.users.me("tok")).rejects.toThrow("Not found");
  });

  it("throws generic error when API returns no detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.resolve({}),
    } as Response);
    await expect(api.users.me("tok")).rejects.toThrow("Request failed");
  });
});

describe("api.auth.login()", () => {
  it("sends credentials as URLSearchParams (not JSON)", async () => {
    const spy = mockFetch({
      access_token: "abc",
      refresh_token: "def",
      token_type: "bearer",
    });
    await api.auth.login("alice", "pass123");
    const call = spy.mock.calls[0];
    expect(call[0]).toBe(`${API_URL}/api/v1/auth/token`);
    expect(call[1]?.method).toBe("POST");
    expect(call[1]?.headers).toEqual(
      expect.objectContaining({
        "Content-Type": "application/x-www-form-urlencoded",
      })
    );
    expect(call[1]?.body).toBeInstanceOf(URLSearchParams);
  });

  it("returns { access_token } response", async () => {
    mockFetch({
      access_token: "abc",
      refresh_token: "def",
      token_type: "bearer",
    });
    const result = await api.auth.login("alice", "pass123");
    expect(result.access_token).toBe("abc");
  });
});

describe("CRUD methods", () => {
  it("constructs correct URL paths", async () => {
    const spy = mockFetch({ id: "t1", name: "Team A" });
    await api.teams.get("tok", "t1");
    expect(spy).toHaveBeenCalledWith(
      `${API_URL}/api/v1/teams/t1`,
      expect.any(Object)
    );
  });

  it("uses correct HTTP methods", async () => {
    let spy = mockFetch({ id: "t1" });
    await api.teams.create("tok", { name: "A", slug: "a" });
    expect(spy.mock.calls[0][1]?.method).toBe("POST");

    vi.restoreAllMocks();
    spy = mockFetch({ id: "t1" });
    await api.teams.update("tok", "t1", { name: "B" });
    expect(spy.mock.calls[0][1]?.method).toBe("PATCH");

    vi.restoreAllMocks();
    spy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.reject(new Error("no body")),
    } as Response);
    await api.teams.delete("tok", "t1");
    expect(spy.mock.calls[0][1]?.method).toBe("DELETE");
  });

  it("conversations.getMessages() builds correct nested URL", async () => {
    const spy = mockFetch([]);
    await api.conversations.getMessages("tok", "conv-1");
    expect(spy).toHaveBeenCalledWith(
      `${API_URL}/api/v1/conversations/conv-1/messages`,
      expect.any(Object)
    );
  });
});

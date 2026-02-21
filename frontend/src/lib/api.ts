const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string;
};

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (opts.token) {
    headers["Authorization"] = `Bearer ${opts.token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type User = {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
  timezone: string;
  is_active: boolean;
};

export type Agent = {
  slug: string;
  name: string;
  description: string;
  capabilities: string[];
};

export type AgentDetail = Agent & {
  instructions: string;
  system_prompt: string;
  module_path: string;
};

export type Task = {
  id: string;
  title: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error: string | null;
  source_channel: string | null;
  created_at: string;
  updated_at: string;
};

export type Event = {
  id: string;
  type: string;
  source_channel: string | null;
  processed: boolean;
  created_at: string;
};

export type Team = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  agent_slugs: string[];
};

export type Workflow = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_enabled: boolean;
};

export type ChannelConfig = {
  id: string;
  type: string;
  is_enabled: boolean;
  config: Record<string, string>;
};

export const api = {
  auth: {
    login: (username: string, password: string) => {
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      return fetch(`${API_URL}/api/v1/auth/token`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: form,
      }).then((r) => r.json()) as Promise<TokenResponse>;
    },
    register: (data: { email: string; username: string; password: string; full_name?: string }) =>
      request<TokenResponse>("/api/v1/auth/register", { method: "POST", body: data }),
  },

  users: {
    me: (token: string) => request<User>("/api/v1/users/me", { token }),
    updateMe: (token: string, data: { full_name?: string; timezone?: string }) =>
      request<User>("/api/v1/users/me", { method: "PATCH", body: data, token }),
    changePassword: (token: string, data: { current_password: string; new_password: string }) =>
      request<{ detail: string }>("/api/v1/users/me/password", { method: "POST", body: data, token }),
  },

  agents: {
    list: (token: string) => request<Agent[]>("/api/v1/agents/", { token }),
    get: (token: string, slug: string) => request<AgentDetail>(`/api/v1/agents/${slug}`, { token }),
  },

  tasks: {
    list: (token: string) => request<Task[]>("/api/v1/tasks/", { token }),
    get: (token: string, id: string) => request<Task>(`/api/v1/tasks/${id}`, { token }),
  },

  events: {
    list: (token: string) => request<Event[]>("/api/v1/events/", { token }),
  },

  teams: {
    list: (token: string) => request<Team[]>("/api/v1/teams/", { token }),
    create: (token: string, data: { name: string; slug: string; description?: string; goal?: string; agent_slugs?: string[] }) =>
      request<Team>("/api/v1/teams/", { method: "POST", body: data, token }),
    update: (token: string, id: string, data: { name?: string; description?: string; goal?: string; agent_slugs?: string[] }) =>
      request<Team>(`/api/v1/teams/${id}`, { method: "PATCH", body: data, token }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/teams/${id}`, { method: "DELETE", token }),
  },

  workflows: {
    list: (token: string) => request<Workflow[]>("/api/v1/workflows/", { token }),
    create: (token: string, data: { name: string; slug: string; description?: string; trigger_event?: string; is_enabled?: boolean }) =>
      request<Workflow>("/api/v1/workflows/", { method: "POST", body: data, token }),
    update: (token: string, id: string, data: Partial<Workflow>) =>
      request<Workflow>(`/api/v1/workflows/${id}`, { method: "PATCH", body: data, token }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/workflows/${id}`, { method: "DELETE", token }),
  },

  channels: {
    list: (token: string) => request<ChannelConfig[]>("/api/v1/channels/", { token }),
    upsert: (token: string, type: string, body: { is_enabled: boolean; config: Record<string, string> }) =>
      request<ChannelConfig>(`/api/v1/channels/${type}`, { method: "PUT", body, token }),
  },

  prompts: {
    list: (token: string) => request<{ name: string; content: string }[]>("/api/v1/prompts/", { token }),
    get: (token: string, name: string) => request<{ name: string; content: string }>(`/api/v1/prompts/${name}`, { token }),
    update: (token: string, name: string, content: string) =>
      request<{ name: string; content: string }>(`/api/v1/prompts/${name}`, { method: "PUT", body: { content }, token }),
    delete: (token: string, name: string) =>
      request<{ detail: string }>(`/api/v1/prompts/${name}`, { method: "DELETE", token }),
    reset: (token: string) =>
      request<{ detail: string }>("/api/v1/prompts/reset", { method: "POST", token }),
  },
};

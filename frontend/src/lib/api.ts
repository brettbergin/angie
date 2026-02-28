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
  category: string;
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
  goal: string | null;
  agent_slugs: string[];
  is_enabled: boolean;
};

export type Workflow = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_enabled: boolean;
};

export type Schedule = {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  cron_expression: string;
  cron_human: string;
  agent_slug: string | null;
  task_payload: Record<string, unknown>;
  is_enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ChannelConfig = {
  id: string;
  type: string;
  is_enabled: boolean;
  config: Record<string, string>;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type PaginatedConversations = {
  items: Conversation[];
  total: number;
  has_more: boolean;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  agent_slug?: string | null;
  created_at: string;
};

export type ConnectionStatus =
  | "connected"
  | "expired"
  | "error"
  | "disconnected";
export type AuthType = "oauth2" | "api_key" | "token" | "credentials";

export type ServiceField = {
  key: string;
  label: string;
  type: string;
};

export type ServiceDefinition = {
  key: string;
  name: string;
  description: string;
  auth_type: AuthType;
  color: string;
  fields: ServiceField[];
  agent_slug: string | null;
};

export type Connection = {
  id: string;
  service_type: string;
  display_name: string | null;
  auth_type: AuthType;
  status: ConnectionStatus;
  masked_credentials: Record<string, string>;
  scopes: string | null;
  token_expires_at: string | null;
  last_used_at: string | null;
  last_tested_at: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type TestResult = {
  success: boolean;
  message: string;
  status: ConnectionStatus;
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
    register: (data: {
      email: string;
      username: string;
      password: string;
      full_name?: string;
    }) =>
      request<TokenResponse>("/api/v1/auth/register", {
        method: "POST",
        body: data,
      }),
  },

  users: {
    me: (token: string) => request<User>("/api/v1/users/me", { token }),
    updateMe: (
      token: string,
      data: { full_name?: string; timezone?: string }
    ) =>
      request<User>("/api/v1/users/me", { method: "PATCH", body: data, token }),
    changePassword: (
      token: string,
      data: { current_password: string; new_password: string }
    ) =>
      request<{ detail: string }>("/api/v1/users/me/password", {
        method: "POST",
        body: data,
        token,
      }),
  },

  agents: {
    list: (token: string) => request<Agent[]>("/api/v1/agents/", { token }),
    get: (token: string, slug: string) =>
      request<AgentDetail>(`/api/v1/agents/${slug}`, { token }),
  },

  tasks: {
    list: (token: string) => request<Task[]>("/api/v1/tasks/", { token }),
    get: (token: string, id: string) =>
      request<Task>(`/api/v1/tasks/${id}`, { token }),
  },

  events: {
    list: (token: string) => request<Event[]>("/api/v1/events/", { token }),
  },

  teams: {
    list: (token: string, enabledOnly?: boolean) =>
      request<Team[]>(
        `/api/v1/teams/${enabledOnly ? "?enabled_only=true" : ""}`,
        { token }
      ),
    get: (token: string, id: string) =>
      request<Team>(`/api/v1/teams/${id}`, { token }),
    create: (
      token: string,
      data: {
        name: string;
        slug: string;
        description?: string;
        goal?: string;
        agent_slugs?: string[];
        is_enabled?: boolean;
      }
    ) => request<Team>("/api/v1/teams/", { method: "POST", body: data, token }),
    update: (
      token: string,
      id: string,
      data: {
        name?: string;
        description?: string;
        goal?: string;
        agent_slugs?: string[];
        is_enabled?: boolean;
      }
    ) =>
      request<Team>(`/api/v1/teams/${id}`, {
        method: "PATCH",
        body: data,
        token,
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/teams/${id}`, { method: "DELETE", token }),
  },

  workflows: {
    list: (token: string) =>
      request<Workflow[]>("/api/v1/workflows/", { token }),
    create: (
      token: string,
      data: {
        name: string;
        slug: string;
        description?: string;
        trigger_event?: string;
        is_enabled?: boolean;
      }
    ) =>
      request<Workflow>("/api/v1/workflows/", {
        method: "POST",
        body: data,
        token,
      }),
    update: (token: string, id: string, data: Partial<Workflow>) =>
      request<Workflow>(`/api/v1/workflows/${id}`, {
        method: "PATCH",
        body: data,
        token,
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/workflows/${id}`, { method: "DELETE", token }),
  },

  schedules: {
    list: (token: string) =>
      request<Schedule[]>("/api/v1/schedules/", { token }),
    create: (
      token: string,
      data: {
        name: string;
        description?: string;
        cron_expression: string;
        agent_slug?: string;
        task_payload?: Record<string, unknown>;
        is_enabled?: boolean;
      }
    ) =>
      request<Schedule>("/api/v1/schedules/", {
        method: "POST",
        body: data,
        token,
      }),
    get: (token: string, id: string) =>
      request<Schedule>(`/api/v1/schedules/${id}`, { token }),
    update: (token: string, id: string, data: Partial<Schedule>) =>
      request<Schedule>(`/api/v1/schedules/${id}`, {
        method: "PATCH",
        body: data,
        token,
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/schedules/${id}`, { method: "DELETE", token }),
    toggle: (token: string, id: string) =>
      request<Schedule>(`/api/v1/schedules/${id}/toggle`, {
        method: "PATCH",
        token,
      }),
  },

  channels: {
    list: (token: string) =>
      request<ChannelConfig[]>("/api/v1/channels/", { token }),
    upsert: (
      token: string,
      type: string,
      body: { is_enabled: boolean; config: Record<string, string> }
    ) =>
      request<ChannelConfig>(`/api/v1/channels/${type}`, {
        method: "PUT",
        body,
        token,
      }),
  },

  prompts: {
    definitions: (token: string) =>
      request<
        {
          name: string;
          label: string;
          description: string;
          placeholder: string;
        }[]
      >("/api/v1/prompts/definitions", { token }),
    list: (token: string) =>
      request<{ name: string; content: string }[]>("/api/v1/prompts/", {
        token,
      }),
    get: (token: string, name: string) =>
      request<{ name: string; content: string }>(`/api/v1/prompts/${name}`, {
        token,
      }),
    update: (token: string, name: string, content: string) =>
      request<{ name: string; content: string }>(`/api/v1/prompts/${name}`, {
        method: "PUT",
        body: { content },
        token,
      }),
    delete: (token: string, name: string) =>
      request<{ detail: string }>(`/api/v1/prompts/${name}`, {
        method: "DELETE",
        token,
      }),
    reset: (token: string) =>
      request<{ detail: string }>("/api/v1/prompts/reset", {
        method: "POST",
        token,
      }),
  },

  conversations: {
    list: (token: string, params?: { limit?: number; offset?: number }) =>
      request<PaginatedConversations>(
        `/api/v1/conversations/?limit=${params?.limit ?? 20}&offset=${params?.offset ?? 0}`,
        { token }
      ),
    create: (token: string, title?: string) =>
      request<Conversation>("/api/v1/conversations/", {
        method: "POST",
        body: { title },
        token,
      }),
    get: (token: string, id: string) =>
      request<Conversation>(`/api/v1/conversations/${id}`, { token }),
    getMessages: (token: string, id: string) =>
      request<ChatMessage[]>(`/api/v1/conversations/${id}/messages`, { token }),
    update: (token: string, id: string, title: string) =>
      request<Conversation>(`/api/v1/conversations/${id}`, {
        method: "PATCH",
        body: { title },
        token,
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/conversations/${id}`, { method: "DELETE", token }),
  },

  connections: {
    services: (token: string) =>
      request<ServiceDefinition[]>("/api/v1/connections/services", { token }),
    list: (token: string) =>
      request<Connection[]>("/api/v1/connections/", { token }),
    get: (token: string, id: string) =>
      request<Connection>(`/api/v1/connections/${id}`, { token }),
    create: (
      token: string,
      data: {
        service_type: string;
        credentials: Record<string, string>;
        display_name?: string;
      }
    ) =>
      request<Connection>("/api/v1/connections/", {
        method: "POST",
        body: data,
        token,
      }),
    update: (
      token: string,
      id: string,
      data: { credentials?: Record<string, string>; display_name?: string }
    ) =>
      request<Connection>(`/api/v1/connections/${id}`, {
        method: "PATCH",
        body: data,
        token,
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/v1/connections/${id}`, { method: "DELETE", token }),
    test: (token: string, id: string) =>
      request<TestResult>(`/api/v1/connections/${id}/test`, {
        method: "POST",
        token,
      }),
  },
};

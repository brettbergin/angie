"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, Agent, Team, ChatMessage as ChatMessageType } from "@/lib/api";
import { parseUTC } from "@/lib/utils";
import { AGENT_COLORS, getAgentColor } from "@/lib/agent-colors";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import {
  MentionAutocomplete,
  MentionItem,
  useMentionKeyboard,
} from "@/components/chat/MentionAutocomplete";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: number;
  type?: "task_result";
  agent_slug?: string | null;
};

function ChatPageInner() {
  const { token, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("c");

  type WsStatus = "disconnected" | "connecting" | "connected";

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const [loadingMessages, setLoadingMessages] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const currentConvoRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingTasksRef = useRef(0);
  const lastMessageTsRef = useRef<string>(""); // ISO timestamp of newest DB message
  const tokenRef = useRef(token);
  const reconnectAttempts = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Skip DB reload when we just created the conversation via WS
  const skipNextReloadRef = useRef(false);

  // Agents & teams for @-mention autocomplete and welcome display
  const [agents, setAgents] = useState<Agent[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [cursorPos, setCursorPos] = useState(0);
  const [showMentions, setShowMentions] = useState(false);

  const mentionItems: MentionItem[] = [
    ...agents.map((a) => ({
      slug: a.slug,
      name: a.name,
      kind: "agent" as const,
    })),
    ...teams.map((t) => ({
      slug: t.slug,
      name: t.name,
      kind: "team" as const,
    })),
  ];

  // Fetch agents and teams on mount
  useEffect(() => {
    if (!token) return;
    api.agents
      .list(token)
      .then(setAgents)
      .catch(() => {});
    api.teams
      .list(token, true)
      .then(setTeams)
      .catch(() => {});
  }, [token]);

  // Keep tokenRef in sync so interval callbacks always use the latest token
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }, []);

  // Load messages when conversation changes
  useEffect(() => {
    if (!token || !conversationId) {
      setMessages([]);
      return;
    }

    // Skip reload when we just created this conversation via WS (we already have messages in state)
    if (skipNextReloadRef.current) {
      skipNextReloadRef.current = false;
      return;
    }

    let cancelled = false;
    setLoadingMessages(true);

    api.conversations
      .getMessages(token, conversationId)
      .then((msgs) => {
        if (cancelled) return;
        const mapped = msgs.map((m: ChatMessageType) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          ts: parseUTC(m.created_at).getTime(),
          agent_slug: m.agent_slug,
          type: m.agent_slug ? ("task_result" as const) : undefined,
        }));
        setMessages(mapped);
        if (msgs.length > 0) {
          lastMessageTsRef.current = msgs[msgs.length - 1].created_at;
        }
        setLoadingMessages(false);
      })
      .catch(() => {
        if (!cancelled) setLoadingMessages(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token, conversationId]);

  // Poll for task results as a safety net (Redis pub/sub is the primary delivery path)
  const startPolling = useCallback((convoId: string) => {
    // If polling is already running, just let it continue — don't restart
    if (pollTimerRef.current) return;
    if (!tokenRef.current) return;
    let attempts = 0;
    const maxAttempts = 30; // 90 seconds at 3s intervals

    const poll = async () => {
      attempts++;
      // Stop polling when no tasks are pending and we've done at least a few checks
      if (pendingTasksRef.current <= 0 && attempts > 3) {
        pollTimerRef.current = null;
        return;
      }
      if (attempts > maxAttempts) {
        pollTimerRef.current = null;
        return;
      }
      const currentToken = tokenRef.current;
      if (!currentToken) return;
      try {
        const msgs = await api.conversations.getMessages(currentToken, convoId);
        const latestTs =
          msgs.length > 0 ? msgs[msgs.length - 1].created_at : "";
        if (latestTs && latestTs > lastMessageTsRef.current) {
          lastMessageTsRef.current = latestTs;
          setMessages(
            msgs.map((m: ChatMessageType) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              ts: parseUTC(m.created_at).getTime(),
              agent_slug: m.agent_slug,
              type: m.agent_slug ? ("task_result" as const) : undefined,
            }))
          );
        }
      } catch {
        // Polling error — ignore and retry
      }
      // Schedule next poll only after current one completes
      pollTimerRef.current = setTimeout(poll, 3000);
    };

    pollTimerRef.current = setTimeout(poll, 3000);
  }, []);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  // WebSocket connection — reconnect when conversation changes
  useEffect(() => {
    if (!token) return;

    // Cancel any pending reconnect
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    // Close previous connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }

    currentConvoRef.current = conversationId;
    reconnectAttempts.current = 0;

    function connectWebSocket() {
      if (!tokenRef.current) return;
      setWsStatus("connecting");

      const wsUrl = currentConvoRef.current
        ? `${WS_URL}/api/v1/chat/ws?token=${tokenRef.current}&conversation_id=${currentConvoRef.current}`
        : `${WS_URL}/api/v1/chat/ws?token=${tokenRef.current}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("connected");
        reconnectAttempts.current = 0;
        // Start heartbeat
        if (heartbeatRef.current) clearInterval(heartbeatRef.current);
        heartbeatRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "ping" }));
          }
        }, 30_000);
      };

      ws.onclose = (event) => {
        setWsStatus("disconnected");
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }
        // Reconnect on unclean close with exponential backoff
        if (!event.wasClean) {
          const delay = Math.min(1000 * 2 ** reconnectAttempts.current, 30_000);
          reconnectAttempts.current++;
          reconnectTimerRef.current = setTimeout(connectWebSocket, delay);
        }
      };

      ws.onerror = () => {
        // onerror is always followed by onclose, so status update happens there
      };

      // Track seen task_result message IDs for robust deduplication
      const seenMessageIds = new Set<string>();

      ws.onmessage = (evt) => {
        const data = JSON.parse(evt.data);

        // Ignore pong responses from heartbeat
        if (data.type === "pong") return;

        // If server created a new conversation, navigate to it
        if (data.conversation_id && !currentConvoRef.current) {
          currentConvoRef.current = data.conversation_id;
          skipNextReloadRef.current = true;
          router.push(`/chat?c=${data.conversation_id}`);
          // Notify sidebar to reload so the new conversation appears
          window.dispatchEvent(new CustomEvent("angie:conversation-created"));
        }

        // Task results for a different conversation — ignore (already persisted in DB)
        if (
          data.type === "task_result" &&
          data.conversation_id &&
          data.conversation_id !== currentConvoRef.current
        ) {
          return;
        }

        // Deduplicate task_result messages by server-generated message_id
        if (data.type === "task_result" && data.message_id) {
          if (seenMessageIds.has(data.message_id)) return;
          seenMessageIds.add(data.message_id);
        }

        // Track pending tasks: increment on dispatch, decrement on result
        if (data.type === "task_result") {
          pendingTasksRef.current = Math.max(0, pendingTasksRef.current - 1);
        }

        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant" as const,
            content: data.content ?? data.message ?? JSON.stringify(data),
            ts: Date.now(),
            type: data.type,
            agent_slug: data.agent_slug,
          },
        ]);

        // If a task was dispatched, bump pending counter and start polling as safety net
        if (data.task_dispatched && currentConvoRef.current) {
          pendingTasksRef.current++;
          startPolling(currentConvoRef.current);
        }
      };
    }

    connectWebSocket();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [token, conversationId, router, startPolling]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function sendMessage(e: React.FormEvent | React.KeyboardEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN)
      return;
    wsRef.current.send(JSON.stringify({ content: text }));
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user" as const,
        content: text,
        ts: Date.now(),
      },
    ]);
    setInput("");
    setShowMentions(false);
    const ta = (e.target as HTMLElement)
      .closest("form")
      ?.querySelector("textarea");
    if (ta) ta.style.height = "auto";
  }

  const handleMentionSelect = useCallback(
    (item: MentionItem) => {
      const before = input.slice(0, cursorPos);
      const atIdx = before.lastIndexOf("@");
      if (atIdx === -1) return;
      const newInput =
        input.slice(0, atIdx) + `@${item.slug} ` + input.slice(cursorPos);
      setInput(newInput);
      setShowMentions(false);
      textareaRef.current?.focus();
    },
    [input, cursorPos]
  );

  const { handleKeyDown: mentionKeyDown } = useMentionKeyboard(
    mentionItems,
    input,
    cursorPos,
    handleMentionSelect,
    showMentions
  );

  const handleTextareaChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      const pos = e.target.selectionStart ?? val.length;
      setInput(val);
      setCursorPos(pos);
      // Show mentions when typing @ followed by optional slug chars
      const before = val.slice(0, pos);
      setShowMentions(/@[a-z0-9_-]*$/i.test(before));
      resizeTextarea();
    },
    [resizeTextarea]
  );

  const handleTextareaKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Let mention autocomplete handle keys first
      if (showMentions && mentionKeyDown(e)) return;
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(e);
      }
    },
    [showMentions, mentionKeyDown]
  );

  // Agent chip click handler — inserts @slug into input
  const handleAgentChipClick = useCallback((slug: string) => {
    setInput((prev) => `@${slug} ${prev}`);
    textareaRef.current?.focus();
  }, []);

  // Shared input area component
  const renderInput = () => (
    <div className="border-t border-gray-800 p-4">
      <form onSubmit={sendMessage} className="relative flex items-end gap-3">
        <div className="relative flex-1">
          <MentionAutocomplete
            items={mentionItems}
            input={input}
            cursorPos={cursorPos}
            onSelect={handleMentionSelect}
            visible={showMentions}
          />
          <textarea
            ref={textareaRef}
            className="max-h-[200px] min-h-[44px] w-full resize-none rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 transition focus:border-transparent focus:outline-none focus:ring-2 focus:ring-angie-500"
            placeholder={
              wsStatus === "connected"
                ? "Message Angie… (type @ to mention an agent)"
                : "Waiting for connection…"
            }
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleTextareaKeyDown}
            disabled={wsStatus !== "connected"}
            rows={1}
          />
        </div>
        <Button
          type="submit"
          disabled={wsStatus !== "connected" || !input.trim()}
          className="h-[44px]"
        >
          {wsStatus === "connecting" ? (
            <Spinner className="h-4 w-4" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );

  // Empty state — no conversation selected
  if (!conversationId) {
    return (
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-gray-100">
              Chat with Angie
            </h1>
            <p className="text-xs text-gray-500">Your personal AI assistant</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                wsStatus === "connected"
                  ? "bg-green-400"
                  : wsStatus === "connecting"
                    ? "animate-pulse bg-amber-400"
                    : "bg-gray-600"
              )}
            />
            {wsStatus === "connecting"
              ? "Connecting…"
              : wsStatus === "connected"
                ? "Connected"
                : "Disconnected"}
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length > 0 ? (
            // Show ephemeral welcome message if received
            messages.map((msg) => (
              <ChatMessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                username={user?.username}
                type={msg.type}
                agentSlug={msg.agent_slug}
                token={token ?? undefined}
              />
            ))
          ) : (
            <div className="flex h-full flex-col items-center justify-center space-y-4 text-gray-500">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-angie-600/30 bg-angie-600/20">
                <span className="text-2xl font-bold text-angie-400">A</span>
              </div>
              <p className="text-lg font-medium text-gray-300">
                Hi, I&apos;m Angie!
              </p>
              <p className="text-center text-sm">
                Start a new chat or select one from the sidebar.
                <br />
                Type <span className="font-mono text-angie-400">@</span> to
                mention an agent.
              </p>
              {agents.length > 0 && (
                <div className="mt-2 max-w-lg space-y-2 text-center">
                  <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Available Agents
                  </p>
                  <div className="flex flex-wrap justify-center gap-1.5">
                    {agents.map((a) => (
                      <button
                        key={a.slug}
                        onClick={() => handleAgentChipClick(a.slug)}
                        className={cn(
                          "cursor-pointer rounded-md border bg-gray-800 px-2 py-1 text-xs transition-colors hover:bg-gray-700",
                          getAgentColor(a.slug).chipBorder,
                          getAgentColor(a.slug).chipText
                        )}
                        title={a.description}
                      >
                        @{a.slug}
                      </button>
                    ))}
                  </div>
                  {teams.length > 0 && (
                    <>
                      <p className="mt-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                        Teams
                      </p>
                      <div className="flex flex-wrap justify-center gap-1.5">
                        {teams.map((t) => (
                          <button
                            key={t.slug}
                            onClick={() => handleAgentChipClick(t.slug)}
                            className="cursor-pointer rounded-md border border-blue-700/40 bg-gray-800 px-2 py-1 text-xs text-blue-400 transition-colors hover:border-blue-500/50 hover:bg-gray-700"
                            title={t.description ?? `Team: ${t.name}`}
                          >
                            @{t.slug}
                          </button>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {renderInput()}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">
            Chat with Angie
          </h1>
          <p className="text-xs text-gray-500">Your personal AI assistant</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              wsStatus === "connected"
                ? "bg-green-400"
                : wsStatus === "connecting"
                  ? "animate-pulse bg-amber-400"
                  : "bg-gray-600"
            )}
          />
          {wsStatus === "connecting"
            ? "Connecting…"
            : wsStatus === "connected"
              ? "Connected"
              : "Disconnected"}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        {loadingMessages && (
          <div className="flex justify-center py-8">
            <Spinner className="h-6 w-6" />
          </div>
        )}

        {!loadingMessages && messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center space-y-4 text-gray-500">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-angie-600/30 bg-angie-600/20">
              <span className="text-2xl font-bold text-angie-400">A</span>
            </div>
            <p className="text-lg font-medium text-gray-300">
              Hi, I&apos;m Angie!
            </p>
            <p className="text-center text-sm">
              Ask me anything or give me a task.
              <br />
              Type <span className="font-mono text-angie-400">@</span> to
              mention an agent.
            </p>
            {agents.length > 0 && (
              <div className="max-w-lg space-y-2 text-center">
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                  Available Agents
                </p>
                <div className="flex flex-wrap justify-center gap-1.5">
                  {agents.map((a) => (
                    <button
                      key={a.slug}
                      onClick={() => handleAgentChipClick(a.slug)}
                      className="cursor-pointer rounded-md border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-angie-400 transition-colors hover:border-angie-500/50 hover:bg-gray-700"
                      title={a.description}
                    >
                      @{a.slug}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessageBubble
            key={msg.id}
            role={msg.role}
            content={msg.content}
            username={user?.username}
            type={msg.type}
            agentSlug={msg.agent_slug}
            token={token ?? undefined}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      {renderInput()}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense>
      <ChatPageInner />
    </Suspense>
  );
}

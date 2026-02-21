"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, Agent, Team, ChatMessage as ChatMessageType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
import { MentionAutocomplete, MentionItem, useMentionKeyboard } from "@/components/chat/MentionAutocomplete";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: number;
  type?: "task_result";
};

function ChatPageInner() {
  const { token, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("c");

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const currentConvoRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messageCountRef = useRef<number>(0);
  const tokenRef = useRef(token);
  // Skip DB reload when we just created the conversation via WS
  const skipNextReloadRef = useRef(false);

  // Agents & teams for @-mention autocomplete and welcome display
  const [agents, setAgents] = useState<Agent[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [cursorPos, setCursorPos] = useState(0);
  const [showMentions, setShowMentions] = useState(false);

  const mentionItems: MentionItem[] = [
    ...agents.map((a) => ({ slug: a.slug, name: a.name, kind: "agent" as const })),
    ...teams.map((t) => ({ slug: t.slug, name: t.name, kind: "team" as const })),
  ];

  // Fetch agents and teams on mount
  useEffect(() => {
    if (!token) return;
    api.agents.list(token).then(setAgents).catch(() => {});
    api.teams.list(token).then(setTeams).catch(() => {});
  }, [token]);

  // Keep tokenRef in sync so interval callbacks always use the latest token
  useEffect(() => { tokenRef.current = token; }, [token]);

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

    api.conversations.getMessages(token, conversationId).then((msgs) => {
      if (cancelled) return;
      const mapped = msgs.map((m: ChatMessageType) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        ts: new Date(m.created_at).getTime(),
      }));
      setMessages(mapped);
      messageCountRef.current = mapped.length;
      setLoadingMessages(false);
    }).catch(() => {
      if (!cancelled) setLoadingMessages(false);
    });

    return () => { cancelled = true; };
  }, [token, conversationId]);

  // Poll for task results (worker persists to DB; WebSocket push from worker is unreliable)
  const startPolling = useCallback((convoId: string) => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    if (!tokenRef.current) return;
    let attempts = 0;
    const maxAttempts = 20; // 60 seconds at 3s intervals

    const poll = async () => {
      attempts++;
      if (attempts > maxAttempts) {
        pollTimerRef.current = null;
        return;
      }
      const currentToken = tokenRef.current;
      if (!currentToken) return;
      try {
        const msgs = await api.conversations.getMessages(currentToken, convoId);
        if (msgs.length > messageCountRef.current) {
          setMessages(
            msgs.map((m: ChatMessageType) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              ts: new Date(m.created_at).getTime(),
            }))
          );
          messageCountRef.current = msgs.length;
          pollTimerRef.current = null;
          return; // Stop polling — got new messages
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

    // Close previous connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    currentConvoRef.current = conversationId;
    setConnecting(true);

    const wsUrl = conversationId
      ? `${WS_URL}/api/v1/chat/ws?token=${token}&conversation_id=${conversationId}`
      : `${WS_URL}/api/v1/chat/ws?token=${token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true); setConnecting(false); };
    ws.onclose = () => { setConnected(false); setConnecting(false); };
    ws.onerror = () => setConnecting(false);

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data);

      // If server created a new conversation, navigate to it
      if (data.conversation_id && !currentConvoRef.current) {
        currentConvoRef.current = data.conversation_id;
        skipNextReloadRef.current = true;
        router.push(`/chat?c=${data.conversation_id}`);
      }

      // Task results for a different conversation — ignore (already persisted in DB)
      if (data.type === "task_result" && data.conversation_id && data.conversation_id !== currentConvoRef.current) {
        return;
      }

      setMessages((prev) => {
        const updated = [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: "assistant" as const,
            content: data.content ?? data.message ?? JSON.stringify(data),
            ts: Date.now(),
            type: data.type,
          },
        ];
        messageCountRef.current = updated.length;
        return updated;
      });

      // If a task was dispatched, start polling for the result
      if (data.task_dispatched && currentConvoRef.current) {
        startPolling(currentConvoRef.current);
      }
    };

    return () => ws.close();
  }, [token, conversationId, router, startPolling]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function sendMessage(e: React.FormEvent | React.KeyboardEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ content: text }));
    setMessages((prev) => {
      const updated = [
        ...prev,
        { id: crypto.randomUUID(), role: "user" as const, content: text, ts: Date.now() },
      ];
      messageCountRef.current = updated.length;
      return updated;
    });
    setInput("");
    setShowMentions(false);
    const ta = (e.target as HTMLElement).closest("form")?.querySelector("textarea");
    if (ta) ta.style.height = "auto";
  }

  const handleMentionSelect = useCallback((item: MentionItem) => {
    const before = input.slice(0, cursorPos);
    const atIdx = before.lastIndexOf("@");
    if (atIdx === -1) return;
    const newInput = input.slice(0, atIdx) + `@${item.slug} ` + input.slice(cursorPos);
    setInput(newInput);
    setShowMentions(false);
    textareaRef.current?.focus();
  }, [input, cursorPos]);

  const { handleKeyDown: mentionKeyDown } = useMentionKeyboard(
    mentionItems, input, cursorPos, handleMentionSelect, showMentions
  );

  const handleTextareaChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const pos = e.target.selectionStart ?? val.length;
    setInput(val);
    setCursorPos(pos);
    // Show mentions when typing @ followed by optional slug chars
    const before = val.slice(0, pos);
    setShowMentions(/@[a-z0-9_-]*$/i.test(before));
    resizeTextarea();
  }, [resizeTextarea]);

  const handleTextareaKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Let mention autocomplete handle keys first
    if (showMentions && mentionKeyDown(e)) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  }, [showMentions, mentionKeyDown]); // eslint-disable-line react-hooks/exhaustive-deps

  // Agent chip click handler — inserts @slug into input
  const handleAgentChipClick = useCallback((slug: string) => {
    setInput((prev) => `@${slug} ${prev}`);
    textareaRef.current?.focus();
  }, []);

  // Shared input area component
  const renderInput = () => (
    <div className="p-4 border-t border-gray-800">
      <form onSubmit={sendMessage} className="relative flex gap-3 items-end">
        <div className="flex-1 relative">
          <MentionAutocomplete
            items={mentionItems}
            input={input}
            cursorPos={cursorPos}
            onSelect={handleMentionSelect}
            visible={showMentions}
          />
          <textarea
            ref={textareaRef}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-angie-500 focus:border-transparent transition resize-none min-h-[44px] max-h-[200px]"
            placeholder={connected ? "Message Angie… (type @ to mention an agent)" : "Waiting for connection…"}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleTextareaKeyDown}
            disabled={!connected}
            rows={1}
          />
        </div>
        <Button type="submit" disabled={!connected || !input.trim()} className="h-[44px]">
          {connecting ? <Spinner className="w-4 h-4" /> : <Send className="w-4 h-4" />}
        </Button>
      </form>
    </div>
  );

  // Empty state — no conversation selected
  if (!conversationId) {
    return (
      <div className="flex flex-col h-full">
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-100">Chat with Angie</h1>
            <p className="text-xs text-gray-500">Your personal AI assistant</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span className={cn("w-2 h-2 rounded-full", connected ? "bg-green-400" : "bg-gray-600")} />
            {connecting ? "Connecting…" : connected ? "Connected" : "Disconnected"}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length > 0 ? (
            // Show ephemeral welcome message if received
            messages.map((msg) => (
              <ChatMessageBubble key={msg.id} role={msg.role} content={msg.content} username={user?.username} />
            ))
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-angie-600/20 border border-angie-600/30 flex items-center justify-center">
                <span className="text-angie-400 font-bold text-2xl">A</span>
              </div>
              <p className="text-lg font-medium text-gray-300">Hi, I&apos;m Angie!</p>
              <p className="text-sm text-center">Start a new chat or select one from the sidebar.<br />Type <span className="text-angie-400 font-mono">@</span> to mention an agent.</p>
              {agents.length > 0 && (
                <div className="max-w-lg text-center space-y-2 mt-2">
                  <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Available Agents</p>
                  <div className="flex flex-wrap gap-1.5 justify-center">
                    {agents.map((a) => (
                      <button
                        key={a.slug}
                        onClick={() => handleAgentChipClick(a.slug)}
                        className="px-2 py-1 rounded-md bg-gray-800 border border-gray-700 text-xs text-angie-400 hover:bg-gray-700 hover:border-angie-500/50 transition-colors cursor-pointer"
                        title={a.description}
                      >
                        @{a.slug}
                      </button>
                    ))}
                  </div>
                  {teams.length > 0 && (
                    <>
                      <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold mt-3">Teams</p>
                      <div className="flex flex-wrap gap-1.5 justify-center">
                        {teams.map((t) => (
                          <button
                            key={t.slug}
                            onClick={() => handleAgentChipClick(t.slug)}
                            className="px-2 py-1 rounded-md bg-gray-800 border border-blue-700/40 text-xs text-blue-400 hover:bg-gray-700 hover:border-blue-500/50 transition-colors cursor-pointer"
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
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-gray-100">Chat with Angie</h1>
          <p className="text-xs text-gray-500">Your personal AI assistant</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className={cn("w-2 h-2 rounded-full", connected ? "bg-green-400" : "bg-gray-600")} />
          {connecting ? "Connecting…" : connected ? "Connected" : "Disconnected"}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {loadingMessages && (
          <div className="flex justify-center py-8">
            <Spinner className="w-6 h-6" />
          </div>
        )}

        {!loadingMessages && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-angie-600/20 border border-angie-600/30 flex items-center justify-center">
              <span className="text-angie-400 font-bold text-2xl">A</span>
            </div>
            <p className="text-lg font-medium text-gray-300">Hi, I&apos;m Angie!</p>
            <p className="text-sm text-center">Ask me anything or give me a task.<br />Type <span className="text-angie-400 font-mono">@</span> to mention an agent.</p>
            {agents.length > 0 && (
              <div className="max-w-lg text-center space-y-2">
                <p className="text-xs text-gray-400 uppercase tracking-wider font-semibold">Available Agents</p>
                <div className="flex flex-wrap gap-1.5 justify-center">
                  {agents.map((a) => (
                    <button
                      key={a.slug}
                      onClick={() => handleAgentChipClick(a.slug)}
                      className="px-2 py-1 rounded-md bg-gray-800 border border-gray-700 text-xs text-angie-400 hover:bg-gray-700 hover:border-angie-500/50 transition-colors cursor-pointer"
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

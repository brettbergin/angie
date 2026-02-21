"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, ChatMessage as ChatMessageType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { ChatMessageBubble } from "@/components/chat/ChatMessage";
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
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const messageCountRef = useRef<number>(0);
  // Skip DB reload when we just created the conversation via WS
  const skipNextReloadRef = useRef(false);

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
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    if (!token) return;
    let attempts = 0;
    const maxAttempts = 20; // 60 seconds at 3s intervals
    pollTimerRef.current = setInterval(async () => {
      attempts++;
      if (attempts > maxAttempts) {
        if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
        return;
      }
      try {
        const msgs = await api.conversations.getMessages(token, convoId);
        if (msgs.length > messageCountRef.current) {
          // Reload all messages from DB to ensure correct ordering
          // (worker result may be inserted before LLM ack in DB)
          setMessages(
            msgs.map((m: ChatMessageType) => ({
              id: m.id,
              role: m.role as "user" | "assistant",
              content: m.content,
              ts: new Date(m.created_at).getTime(),
            }))
          );
          messageCountRef.current = msgs.length;
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
      } catch {
        // Polling error — ignore and retry
      }
    }, 3000);
  }, [token]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
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
    const ta = (e.target as HTMLElement).closest("form")?.querySelector("textarea");
    if (ta) ta.style.height = "auto";
  }

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
          <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-angie-600/20 border border-angie-600/30 flex items-center justify-center">
              <span className="text-angie-400 font-bold text-2xl">A</span>
            </div>
            <p className="text-lg font-medium text-gray-300">Hi, I&apos;m Angie!</p>
            <p className="text-sm">Start a new chat or select one from the sidebar.</p>
          </div>
        </div>

        {/* Input — starts a new conversation on send */}
        <div className="p-4 border-t border-gray-800">
          <form onSubmit={sendMessage} className="flex gap-3 items-end">
            <textarea
              ref={textareaRef}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-angie-500 focus:border-transparent transition resize-none min-h-[44px] max-h-[200px]"
              placeholder={connected ? "Message Angie…" : "Waiting for connection…"}
              value={input}
              onChange={(e) => { setInput(e.target.value); resizeTextarea(); }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); } }}
              disabled={!connected}
              rows={1}
            />
            <Button type="submit" disabled={!connected || !input.trim()} className="h-[44px]">
              {connecting ? <Spinner className="w-4 h-4" /> : <Send className="w-4 h-4" />}
            </Button>
          </form>
        </div>
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
          <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-angie-600/20 border border-angie-600/30 flex items-center justify-center">
              <span className="text-angie-400 font-bold text-2xl">A</span>
            </div>
            <p className="text-lg font-medium text-gray-300">Hi, I&apos;m Angie!</p>
            <p className="text-sm">Ask me anything or give me a task to complete.</p>
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
      <div className="p-4 border-t border-gray-800">
        <form onSubmit={sendMessage} className="flex gap-3 items-end">
          <textarea
            ref={textareaRef}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-angie-500 focus:border-transparent transition resize-none min-h-[44px] max-h-[200px]"
            placeholder={connected ? "Message Angie…" : "Waiting for connection…"}
            value={input}
            onChange={(e) => { setInput(e.target.value); resizeTextarea(); }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(e); } }}
            disabled={!connected}
            rows={1}
          />
          <Button type="submit" disabled={!connected || !input.trim()} className="h-[44px]">
            {connecting ? <Spinner className="w-4 h-4" /> : <Send className="w-4 h-4" />}
          </Button>
        </form>
      </div>
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

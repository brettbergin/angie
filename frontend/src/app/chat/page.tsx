"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: number;
};

export default function ChatPage() {
  const { token, user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!token) return;
    setConnecting(true);
    const ws = new WebSocket(`${WS_URL}/api/v1/chat/ws?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true); setConnecting(false); };
    ws.onclose = () => { setConnected(false); setConnecting(false); };
    ws.onerror = () => setConnecting(false);

    ws.onmessage = (evt) => {
      const data = JSON.parse(evt.data);
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: data.content ?? data.message ?? JSON.stringify(data), ts: Date.now() },
      ]);
    };

    return () => ws.close();
  }, [token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function sendMessage(e: React.FormEvent | React.KeyboardEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ content: text }));
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: text, ts: Date.now() },
    ]);
    setInput("");
    const ta = (e.target as HTMLElement).closest("form")?.querySelector("textarea");
    if (ta) ta.style.height = "auto";
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
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-angie-600/20 border border-angie-600/30 flex items-center justify-center">
              <span className="text-angie-400 font-bold text-2xl">A</span>
            </div>
            <p className="text-lg font-medium text-gray-300">Hi, I&apos;m Angie!</p>
            <p className="text-sm">Ask me anything or give me a task to complete.</p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}
          >
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-angie-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 mr-2 mt-0.5">
                A
              </div>
            )}
            <div
              className={cn(
                "max-w-lg px-4 py-3 rounded-2xl text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-angie-600 text-white rounded-tr-sm"
                  : "bg-gray-800 text-gray-100 rounded-tl-sm"
              )}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-invert prose-sm max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0.5 prose-pre:my-2 prose-code:text-angie-300 prose-a:text-angie-400 prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ml-2 mt-0.5">
                {user?.username[0].toUpperCase() ?? "U"}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800">
        <form onSubmit={sendMessage} className="flex gap-3 items-end">
          <textarea
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-100 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-angie-500 focus:border-transparent transition resize-none min-h-[44px] max-h-[200px]"
            placeholder={connected ? "Message Angie…" : "Waiting for connection…"}
            value={input}
            onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = e.target.scrollHeight + "px"; }}
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

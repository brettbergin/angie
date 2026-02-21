"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, Conversation } from "@/lib/api";
import { cn } from "@/lib/utils";
import { MessageSquarePlus, Trash2, Pencil, Check, X } from "lucide-react";

type Props = {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export function ConversationSidebar({ activeId, onSelect, onNew, refreshKey }: Props) {
  const { token } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const editRef = useRef<HTMLInputElement>(null);
  const deletingRef = useRef<string | null>(null);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api.conversations.list(token);
      const removing = deletingRef.current;
      setConversations(removing ? data.filter((c) => c.id !== removing) : data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations, refreshKey, activeId]);

  useEffect(() => {
    if (editingId && editRef.current) {
      editRef.current.focus();
      editRef.current.select();
    }
  }, [editingId]);

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (!token) return;
    try {
      deletingRef.current = id;
      await api.conversations.delete(token, id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) onNew();
      deletingRef.current = null;
    } catch {
      deletingRef.current = null;
    }
  }

  function startRename(e: React.MouseEvent, convo: Conversation) {
    e.stopPropagation();
    setEditingId(convo.id);
    setEditTitle(convo.title);
  }

  async function saveRename(id: string) {
    if (!token || !editTitle.trim()) {
      setEditingId(null);
      return;
    }
    try {
      const updated = await api.conversations.update(token, id, editTitle.trim());
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch {
      // ignore
    }
    setEditingId(null);
  }

  return (
    <div className="w-72 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
      <div className="p-3 border-b border-gray-800">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg bg-angie-600 hover:bg-angie-500 text-white text-sm font-medium transition-colors"
        >
          <MessageSquarePlus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {loading && (
          <p className="text-xs text-gray-500 text-center py-4">Loading…</p>
        )}

        {!loading && conversations.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-4">No conversations yet</p>
        )}

        {conversations.map((convo) => (
          <div
            key={convo.id}
            onClick={() => onSelect(convo.id)}
            className={cn(
              "group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors text-sm",
              activeId === convo.id
                ? "bg-angie-600/20 text-angie-400 border border-angie-600/30"
                : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
            )}
          >
            {editingId === convo.id ? (
              <div className="flex-1 flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <input
                  ref={editRef}
                  className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-0.5 text-xs text-gray-100 focus:outline-none focus:border-angie-500"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveRename(convo.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                />
                <button
                  onClick={() => saveRename(convo.id)}
                  className="p-0.5 text-green-400 hover:text-green-300"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-0.5 text-gray-500 hover:text-gray-300"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <>
                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium">{convo.title}</p>
                  <p className="text-xs text-gray-600 mt-0.5">
                    {timeAgo(convo.updated_at)}
                  </p>
                </div>
                <div className="hidden group-hover:flex items-center gap-0.5 flex-shrink-0">
                  <button
                    onClick={(e) => startRename(e, convo)}
                    className="p-1 text-gray-500 hover:text-gray-300 transition-colors"
                    title="Rename"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={(e) => handleDelete(e, convo.id)}
                    className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

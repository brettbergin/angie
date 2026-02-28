"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, Conversation } from "@/lib/api";
import { cn, parseUTC } from "@/lib/utils";
import {
  MessageSquarePlus,
  Trash2,
  Pencil,
  Check,
  X,
  Loader2,
} from "lucide-react";

const PAGE_SIZE = 20;

type Props = {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  refreshKey: number;
};

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - parseUTC(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export function ConversationSidebar({
  activeId,
  onSelect,
  onNew,
  refreshKey,
}: Props) {
  const { token } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const editRef = useRef<HTMLInputElement>(null);
  const deletingRef = useRef<string | null>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef(0);
  const loadingMoreRef = useRef(false);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    try {
      const data = await api.conversations.list(token, {
        limit: PAGE_SIZE,
        offset: 0,
      });
      const removing = deletingRef.current;
      const items = removing
        ? data.items.filter((c) => c.id !== removing)
        : data.items;
      setConversations(items);
      setHasMore(data.has_more);
      offsetRef.current = PAGE_SIZE;
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token]);

  const loadMore = useCallback(async () => {
    if (!token || loadingMoreRef.current || !hasMore) return;
    loadingMoreRef.current = true;
    setLoadingMore(true);
    try {
      const data = await api.conversations.list(token, {
        limit: PAGE_SIZE,
        offset: offsetRef.current,
      });
      setConversations((prev) => [...prev, ...data.items]);
      setHasMore(data.has_more);
      offsetRef.current += PAGE_SIZE;
    } catch {
      // ignore
    } finally {
      loadingMoreRef.current = false;
      setLoadingMore(false);
    }
  }, [token, hasMore]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations, refreshKey]);

  // Reload when a new conversation is created via WebSocket.
  // The chat page fires this custom event after router.push to the new conversation.
  useEffect(() => {
    const handler = () => loadConversations();
    window.addEventListener("angie:conversation-created", handler);
    return () =>
      window.removeEventListener("angie:conversation-created", handler);
  }, [loadConversations]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { threshold: 0.1 }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMore]);

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
      const updated = await api.conversations.update(
        token,
        id,
        editTitle.trim()
      );
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch {
      // ignore
    }
    setEditingId(null);
  }

  return (
    <div className="flex h-full w-72 flex-col border-r border-gray-800 bg-gray-900">
      <div className="border-b border-gray-800 p-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-lg bg-angie-600 px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-angie-500"
        >
          <MessageSquarePlus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {loading && (
          <p className="py-4 text-center text-xs text-gray-500">Loading…</p>
        )}

        {!loading && conversations.length === 0 && (
          <p className="py-4 text-center text-xs text-gray-500">
            No conversations yet
          </p>
        )}

        {conversations.map((convo) => (
          <div
            key={convo.id}
            onClick={() => onSelect(convo.id)}
            className={cn(
              "group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2.5 text-sm transition-colors",
              activeId === convo.id
                ? "border border-angie-600/30 bg-angie-600/20 text-angie-400"
                : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
            )}
          >
            {editingId === convo.id ? (
              <div
                className="flex flex-1 items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <input
                  ref={editRef}
                  className="flex-1 rounded border border-gray-600 bg-gray-800 px-2 py-0.5 text-xs text-gray-100 focus:border-angie-500 focus:outline-none"
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
                  <Check className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="p-0.5 text-gray-500 hover:text-gray-300"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ) : (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{convo.title}</p>
                  <p className="mt-0.5 text-xs text-gray-600">
                    {timeAgo(convo.updated_at)}
                  </p>
                </div>
                <div className="hidden flex-shrink-0 items-center gap-0.5 group-hover:flex">
                  <button
                    onClick={(e) => startRename(e, convo)}
                    className="p-1 text-gray-500 transition-colors hover:text-gray-300"
                    title="Rename"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={(e) => handleDelete(e, convo.id)}
                    className="p-1 text-gray-500 transition-colors hover:text-red-400"
                    title="Delete"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}

        {loadingMore && (
          <div className="flex justify-center py-3">
            <Loader2 className="h-4 w-4 animate-spin text-gray-500" />
          </div>
        )}
        <div ref={sentinelRef} className="h-1" />
      </div>
    </div>
  );
}

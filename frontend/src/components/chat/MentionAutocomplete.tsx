"use client";

import type React from "react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type MentionItem = {
  slug: string;
  name: string;
  kind: "agent" | "team";
};

type Props = {
  items: MentionItem[];
  input: string;
  cursorPos: number;
  onSelect: (item: MentionItem) => void;
  visible: boolean;
};

export function MentionAutocomplete({ items, input, cursorPos, onSelect, visible }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Extract the @query from the input at cursor position
  const query = (() => {
    const before = input.slice(0, cursorPos);
    const match = before.match(/@([a-z0-9_-]*)$/i);
    return match ? match[1].toLowerCase() : null;
  })();

  const filtered = query !== null
    ? items.filter((i) => i.slug.includes(query) || i.name.toLowerCase().includes(query))
    : [];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const el = listRef.current.children[selectedIndex] as HTMLElement;
      el?.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!visible || query === null || filtered.length === 0) return null;

  return (
    <div
      ref={listRef}
      className="absolute bottom-full mb-1 left-0 right-0 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-48 overflow-y-auto z-50"
    >
      {filtered.map((item, i) => (
        <button
          key={`${item.kind}-${item.slug}`}
          type="button"
          className={cn(
            "w-full text-left px-3 py-2 text-sm flex items-center gap-2 hover:bg-gray-700 transition-colors",
            i === selectedIndex && "bg-gray-700"
          )}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(item);
          }}
          onMouseEnter={() => setSelectedIndex(i)}
        >
          <span className={cn(
            "w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold flex-shrink-0",
            item.kind === "team" ? "bg-blue-600/30 text-blue-400" : "bg-angie-600/30 text-angie-400"
          )}>
            {item.kind === "team" ? "T" : "@"}
          </span>
          <span className="text-gray-100 font-medium">@{item.slug}</span>
          <span className="text-gray-500 text-xs truncate">{item.name}</span>
          {item.kind === "team" && (
            <span className="ml-auto text-[10px] text-blue-400 font-medium uppercase">team</span>
          )}
        </button>
      ))}
    </div>
  );
}

/**
 * Hook to handle keyboard navigation for the autocomplete.
 * Returns a keydown handler to attach to the textarea.
 */
export function useMentionKeyboard(
  items: MentionItem[],
  input: string,
  cursorPos: number,
  onSelect: (item: MentionItem) => void,
  visible: boolean,
) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const query = (() => {
    const before = input.slice(0, cursorPos);
    const match = before.match(/@([a-z0-9_-]*)$/i);
    return match ? match[1].toLowerCase() : null;
  })();

  const filtered = query !== null
    ? items.filter((i) => i.slug.includes(query) || i.name.toLowerCase().includes(query))
    : [];

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!visible || filtered.length === 0) return false;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filtered.length);
      return true;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
      return true;
    }
    if (e.key === "Enter" || e.key === "Tab") {
      if (filtered[selectedIndex]) {
        e.preventDefault();
        onSelect(filtered[selectedIndex]);
        return true;
      }
    }
    if (e.key === "Escape") {
      return true; // Let parent handle closing
    }
    return false;
  };

  return { handleKeyDown, selectedIndex, filtered };
}

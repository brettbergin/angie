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

export function MentionAutocomplete({
  items,
  input,
  cursorPos,
  onSelect,
  visible,
}: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  // Extract the @query from the input at cursor position
  const query = (() => {
    const before = input.slice(0, cursorPos);
    const match = before.match(/@([a-z0-9_-]*)$/i);
    return match ? match[1].toLowerCase() : null;
  })();

  const filtered =
    query !== null
      ? items.filter(
          (i) => i.slug.includes(query) || i.name.toLowerCase().includes(query)
        )
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
      className="absolute bottom-full left-0 right-0 z-50 mb-1 max-h-48 overflow-y-auto rounded-lg border border-gray-700 bg-gray-800 shadow-xl"
    >
      {filtered.map((item, i) => (
        <button
          key={`${item.kind}-${item.slug}`}
          type="button"
          className={cn(
            "flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-gray-700",
            i === selectedIndex && "bg-gray-700"
          )}
          onMouseDown={(e) => {
            e.preventDefault();
            onSelect(item);
          }}
          onMouseEnter={() => setSelectedIndex(i)}
        >
          <span
            className={cn(
              "flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-[10px] font-bold",
              item.kind === "team"
                ? "bg-blue-600/30 text-blue-400"
                : "bg-angie-600/30 text-angie-400"
            )}
          >
            {item.kind === "team" ? "T" : "@"}
          </span>
          <span className="font-medium text-gray-100">@{item.slug}</span>
          <span className="truncate text-xs text-gray-500">{item.name}</span>
          {item.kind === "team" && (
            <span className="ml-auto text-[10px] font-medium uppercase text-blue-400">
              team
            </span>
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
  visible: boolean
) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  const query = (() => {
    const before = input.slice(0, cursorPos);
    const match = before.match(/@([a-z0-9_-]*)$/i);
    return match ? match[1].toLowerCase() : null;
  })();

  const filtered =
    query !== null
      ? items.filter(
          (i) => i.slug.includes(query) || i.name.toLowerCase().includes(query)
        )
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
      setSelectedIndex(
        (prev) => (prev - 1 + filtered.length) % filtered.length
      );
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

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderHook, act } from "@testing-library/react";
import {
  MentionAutocomplete,
  useMentionKeyboard,
  type MentionItem,
} from "../MentionAutocomplete";

const items: MentionItem[] = [
  { slug: "github", name: "GitHub Agent", kind: "agent" },
  { slug: "gmail", name: "Gmail Agent", kind: "agent" },
  { slug: "dev-team", name: "Dev Team", kind: "team" },
  { slug: "ops-team", name: "Ops Team", kind: "team" },
];

describe("MentionAutocomplete", () => {
  it("filters items by slug match (case-insensitive)", () => {
    render(
      <MentionAutocomplete
        items={items}
        input="@git"
        cursorPos={4}
        onSelect={vi.fn()}
        visible={true}
      />
    );
    expect(screen.getByText("@github")).toBeInTheDocument();
    expect(screen.queryByText("@gmail")).not.toBeInTheDocument();
  });

  it("filters items by name match", () => {
    render(
      <MentionAutocomplete
        items={items}
        input="@ops"
        cursorPos={4}
        onSelect={vi.fn()}
        visible={true}
      />
    );
    expect(screen.getByText("@ops-team")).toBeInTheDocument();
  });

  it("shows all items when query is empty (just @)", () => {
    render(
      <MentionAutocomplete
        items={items}
        input="@"
        cursorPos={1}
        onSelect={vi.fn()}
        visible={true}
      />
    );
    expect(screen.getByText("@github")).toBeInTheDocument();
    expect(screen.getByText("@gmail")).toBeInTheDocument();
    expect(screen.getByText("@dev-team")).toBeInTheDocument();
    expect(screen.getByText("@ops-team")).toBeInTheDocument();
  });

  it("returns null when no matches", () => {
    const { container } = render(
      <MentionAutocomplete
        items={items}
        input="@zzzzz"
        cursorPos={6}
        onSelect={vi.fn()}
        visible={true}
      />
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("useMentionKeyboard", () => {
  it("ArrowDown increments selectedIndex with wrap", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useMentionKeyboard(items, "@", 1, onSelect, true)
    );

    expect(result.current.selectedIndex).toBe(0);

    act(() => {
      result.current.handleKeyDown({
        key: "ArrowDown",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    expect(result.current.selectedIndex).toBe(1);

    // Wrap around
    act(() => {
      result.current.handleKeyDown({
        key: "ArrowDown",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    act(() => {
      result.current.handleKeyDown({
        key: "ArrowDown",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    act(() => {
      result.current.handleKeyDown({
        key: "ArrowDown",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    expect(result.current.selectedIndex).toBe(0); // wrapped
  });

  it("ArrowUp decrements selectedIndex with wrap", () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useMentionKeyboard(items, "@", 1, onSelect, true)
    );

    act(() => {
      result.current.handleKeyDown({
        key: "ArrowUp",
        preventDefault: vi.fn(),
      } as unknown as React.KeyboardEvent);
    });
    // Should wrap to last item
    expect(result.current.selectedIndex).toBe(items.length - 1);
  });
});

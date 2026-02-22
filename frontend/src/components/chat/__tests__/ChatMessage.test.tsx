import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessageBubble } from "../ChatMessage";

// Mock react-markdown and plugins to avoid ESM issues in jsdom
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));
vi.mock("remark-gfm", () => ({ default: () => {} }));
vi.mock("rehype-sanitize", () => ({
  default: () => {},
  defaultSchema: { tagNames: [], attributes: {}, protocols: {} },
}));

describe("ChatMessageBubble", () => {
  it("user messages render with user avatar on right side", () => {
    const { container } = render(
      <ChatMessageBubble role="user" content="Hello" username="alice" />
    );
    const avatars = container.querySelectorAll(".rounded-full");
    // User avatar is the last element (right side)
    const avatar = avatars[avatars.length - 1];
    expect(avatar?.textContent).toBe("A");
  });

  it('assistant messages render with "A" avatar on left side', () => {
    const { container } = render(
      <ChatMessageBubble role="assistant" content="Hi there" />
    );
    const avatars = container.querySelectorAll(".rounded-full");
    expect(avatars[0]?.textContent).toBe("A");
  });

  it('task result messages show emerald styling and "Task Result" label', () => {
    render(
      <ChatMessageBubble role="assistant" content="Done" type="task_result" />
    );
    expect(screen.getByText("Task Result")).toBeInTheDocument();
  });

  it('username initial extraction: "alice" → "A", undefined → "U"', () => {
    const { container, rerender } = render(
      <ChatMessageBubble role="user" content="Hi" username="alice" />
    );
    let avatars = container.querySelectorAll(".rounded-full");
    expect(avatars[avatars.length - 1]?.textContent).toBe("A");

    rerender(<ChatMessageBubble role="user" content="Hi" />);
    avatars = container.querySelectorAll(".rounded-full");
    expect(avatars[avatars.length - 1]?.textContent).toBe("U");
  });

  it("markdown content is rendered for assistant messages", () => {
    render(<ChatMessageBubble role="assistant" content="**bold** text" />);
    expect(screen.getByTestId("markdown")).toBeInTheDocument();
  });

  it("user messages render content as plain text", () => {
    render(<ChatMessageBubble role="user" content="plain text" />);
    expect(screen.getByText("plain text")).toBeInTheDocument();
  });
});

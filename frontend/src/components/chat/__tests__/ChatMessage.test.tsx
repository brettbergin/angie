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

  it('task result without agentSlug shows emerald fallback and "Task Result" label', () => {
    const { container } = render(
      <ChatMessageBubble role="assistant" content="Done" type="task_result" />
    );
    expect(screen.getByText("Task Result")).toBeInTheDocument();
    // Fallback avatar should have emerald bg and "A" initial
    const avatar = container.querySelector(".rounded-full");
    expect(avatar?.textContent).toBe("A");
    expect(avatar?.className).toContain("bg-emerald-600");
  });

  it('task result with agentSlug="github" shows green avatar with logo and "github result" label', () => {
    const { container } = render(
      <ChatMessageBubble
        role="assistant"
        content="Repos listed"
        type="task_result"
        agentSlug="github"
      />
    );
    expect(screen.getByText("github result")).toBeInTheDocument();
    const avatar = container.querySelector(".rounded-full");
    expect(avatar?.className).toContain("bg-green-600");
    // Should render the GitHub SVG logo instead of text initial
    expect(avatar?.querySelector("svg")).toBeTruthy();
  });

  it('task result with agentSlug="weather" shows teal avatar and "weather result" label', () => {
    const { container } = render(
      <ChatMessageBubble
        role="assistant"
        content="Sunny today"
        type="task_result"
        agentSlug="weather"
      />
    );
    expect(screen.getByText("weather result")).toBeInTheDocument();
    const avatar = container.querySelector(".rounded-full");
    expect(avatar?.textContent).toBe("W");
    expect(avatar?.className).toContain("bg-teal-600");
  });

  it('task result with agentSlug="cron" shows amber avatar', () => {
    const { container } = render(
      <ChatMessageBubble
        role="assistant"
        content="Scheduled"
        type="task_result"
        agentSlug="cron"
      />
    );
    expect(screen.getByText("cron result")).toBeInTheDocument();
    const avatar = container.querySelector(".rounded-full");
    expect(avatar?.textContent).toBe("C");
    expect(avatar?.className).toContain("bg-amber-600");
  });

  it("non-task-result assistant messages use Angie avatar regardless of agentSlug", () => {
    const { container } = render(
      <ChatMessageBubble role="assistant" content="Hello" agentSlug="github" />
    );
    const avatar = container.querySelector(".rounded-full");
    expect(avatar?.textContent).toBe("A");
    expect(avatar?.className).toContain("bg-angie-600");
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

import { describe, it, expect, vi } from "vitest";
import { timeAgo } from "../ConversationSidebar";

describe("timeAgo()", () => {
  it('returns "just now" for < 1 min ago', () => {
    const now = new Date().toISOString();
    expect(timeAgo(now)).toBe("just now");
  });

  it('returns "30m ago" for 30 minutes ago', () => {
    const date = new Date(Date.now() - 30 * 60_000).toISOString();
    expect(timeAgo(date)).toBe("30m ago");
  });

  it('returns "5h ago" for 5 hours ago', () => {
    const date = new Date(Date.now() - 5 * 60 * 60_000).toISOString();
    expect(timeAgo(date)).toBe("5h ago");
  });

  it('returns "3d ago" for 3 days ago', () => {
    const date = new Date(Date.now() - 3 * 24 * 60 * 60_000).toISOString();
    expect(timeAgo(date)).toBe("3d ago");
  });

  it("returns formatted date for > 7 days ago", () => {
    const date = new Date(Date.now() - 10 * 24 * 60 * 60_000).toISOString();
    const result = timeAgo(date);
    // Should be a locale date string, not relative
    expect(result).not.toContain("ago");
    expect(result).not.toBe("just now");
  });

  it("handles edge case at exactly 1 minute", () => {
    const date = new Date(Date.now() - 60_000).toISOString();
    expect(timeAgo(date)).toBe("1m ago");
  });

  it("handles edge case at exactly 24 hours", () => {
    const date = new Date(Date.now() - 24 * 60 * 60_000).toISOString();
    expect(timeAgo(date)).toBe("1d ago");
  });
});

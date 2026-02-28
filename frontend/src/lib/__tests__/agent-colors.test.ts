import { describe, it, expect } from "vitest";
import { getAgentColor, AGENT_COLORS } from "../agent-colors";

describe("getAgentColor", () => {
  it("returns correct config for all 8 agents", () => {
    const slugs = [
      "cron",
      "task-manager",
      "workflow-manager",
      "event-manager",
      "github",
      "software-dev",
      "web",
      "weather",
    ];
    for (const slug of slugs) {
      const color = getAgentColor(slug);
      expect(color).toBe(AGENT_COLORS[slug]);
      expect(color.avatarBg).toBeTruthy();
      expect(color.initial).toBeTruthy();
    }
  });

  it("returns emerald fallback for null", () => {
    const color = getAgentColor(null);
    expect(color.avatarBg).toBe("bg-emerald-600");
    expect(color.initial).toBe("A");
  });

  it("returns emerald fallback for undefined", () => {
    const color = getAgentColor(undefined);
    expect(color.avatarBg).toBe("bg-emerald-600");
  });

  it("returns emerald fallback for unknown slug", () => {
    const color = getAgentColor("unknown-agent");
    expect(color.avatarBg).toBe("bg-emerald-600");
    expect(color.labelClass).toBe("text-emerald-400");
  });

  it("cron returns amber", () => {
    const color = getAgentColor("cron");
    expect(color.avatarBg).toBe("bg-amber-600");
    expect(color.labelClass).toBe("text-amber-400");
    expect(color.initial).toBe("C");
  });

  it("github returns green with icon", () => {
    const color = getAgentColor("github");
    expect(color.avatarBg).toBe("bg-green-600");
    expect(color.labelClass).toBe("text-green-400");
    expect(color.initial).toBe("G");
    expect(color.icon).toBeDefined();
  });

  it("weather returns teal", () => {
    const color = getAgentColor("weather");
    expect(color.avatarBg).toBe("bg-teal-600");
    expect(color.labelClass).toBe("text-teal-400");
    expect(color.initial).toBe("W");
  });

  it("each agent has all required fields", () => {
    for (const [slug, color] of Object.entries(AGENT_COLORS)) {
      expect(color.avatarBg, `${slug}.avatarBg`).toBeTruthy();
      expect(color.borderClass, `${slug}.borderClass`).toBeTruthy();
      expect(color.bgClass, `${slug}.bgClass`).toBeTruthy();
      expect(color.labelClass, `${slug}.labelClass`).toBeTruthy();
      expect(color.initial, `${slug}.initial`).toHaveLength(1);
      expect(color.chipBorder, `${slug}.chipBorder`).toBeTruthy();
      expect(color.chipText, `${slug}.chipText`).toBeTruthy();
    }
  });
});

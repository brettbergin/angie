import { describe, it, expect } from "vitest";
import { cn, formatDate, parseUTC, statusColor } from "../utils";

describe("cn()", () => {
  it("merges multiple class strings", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("resolves Tailwind conflicts", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });

  it("handles undefined/null/false values", () => {
    expect(cn("foo", undefined, null, false, "bar")).toBe("foo bar");
  });
});

describe("parseUTC()", () => {
  it("appends Z to naive timestamp strings", () => {
    const d = parseUTC("2024-06-15T14:30:00");
    expect(d.toISOString()).toBe("2024-06-15T14:30:00.000Z");
  });

  it("leaves timestamp with Z unchanged", () => {
    const d = parseUTC("2024-06-15T14:30:00Z");
    expect(d.toISOString()).toBe("2024-06-15T14:30:00.000Z");
  });

  it("leaves timestamp with offset unchanged", () => {
    const d = parseUTC("2024-06-15T14:30:00+05:00");
    expect(d.toISOString()).toBe("2024-06-15T09:30:00.000Z");
  });
});

describe("formatDate()", () => {
  it("converts ISO string to locale format", () => {
    const result = formatDate("2024-01-15T12:00:00Z");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("handles invalid input gracefully", () => {
    const result = formatDate("not-a-date");
    expect(result).toBe("Invalid Date");
  });
});

describe("statusColor()", () => {
  it('returns "text-green-400" for success', () => {
    expect(statusColor("success")).toBe("text-green-400");
  });

  it("maps all known statuses correctly", () => {
    expect(statusColor("pending")).toBe("text-yellow-400");
    expect(statusColor("running")).toBe("text-blue-400");
    expect(statusColor("failure")).toBe("text-red-400");
    expect(statusColor("cancelled")).toBe("text-gray-400");
    expect(statusColor("retrying")).toBe("text-orange-400");
    expect(statusColor("queued")).toBe("text-blue-300");
  });

  it('returns default "text-gray-400" for unknown status', () => {
    expect(statusColor("unknown")).toBe("text-gray-400");
    expect(statusColor("")).toBe("text-gray-400");
  });
});

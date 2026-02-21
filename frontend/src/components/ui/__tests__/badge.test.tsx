import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "../badge";

describe("Badge", () => {
  it("renders label text", () => {
    render(<Badge label="Active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies correct color class for each status", () => {
    const { container } = render(<Badge label="OK" status="success" />);
    const span = container.querySelector("span")!;
    expect(span.className).toContain("text-green-400");
  });

  it("falls back to default color for unknown status", () => {
    const { container } = render(<Badge label="mystery" status="unknown" />);
    const span = container.querySelector("span")!;
    expect(span.className).toContain("text-gray-300");
  });

  it("uses label as status key when no status prop", () => {
    const { container } = render(<Badge label="Pending" />);
    const span = container.querySelector("span")!;
    expect(span.className).toContain("text-yellow-400");
  });
});

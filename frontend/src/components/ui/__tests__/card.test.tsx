import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Card } from "../card";

describe("Card", () => {
  it("renders children", () => {
    render(<Card>Hello</Card>);
    expect(screen.getByText("Hello")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(<Card className="my-class">Hi</Card>);
    expect(container.firstElementChild!.className).toContain("my-class");
  });

  it("forwards onClick handler", () => {
    const handler = vi.fn();
    render(<Card onClick={handler}>Click</Card>);
    fireEvent.click(screen.getByText("Click"));
    expect(handler).toHaveBeenCalledOnce();
  });
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "../button";

describe("Button", () => {
  it("renders children text", () => {
    render(<Button>Click me</Button>);
    expect(
      screen.getByRole("button", { name: "Click me" })
    ).toBeInTheDocument();
  });

  it("applies variant classes", () => {
    const { rerender } = render(<Button variant="danger">Del</Button>);
    expect(screen.getByRole("button").className).toContain("bg-red-700");

    rerender(<Button variant="ghost">Ghost</Button>);
    expect(screen.getByRole("button").className).toContain("hover:bg-gray-800");

    rerender(<Button variant="secondary">Sec</Button>);
    expect(screen.getByRole("button").className).toContain("bg-gray-700");
  });

  it("applies size classes", () => {
    const { rerender } = render(<Button size="sm">S</Button>);
    expect(screen.getByRole("button").className).toContain("px-3");

    rerender(<Button size="lg">L</Button>);
    expect(screen.getByRole("button").className).toContain("px-6");
  });

  it("disabled state sets disabled attribute and opacity class", () => {
    render(<Button disabled>No</Button>);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    expect(btn.className).toContain("disabled:opacity-50");
  });

  it("forwards onClick handler", () => {
    const handler = vi.fn();
    render(<Button onClick={handler}>Go</Button>);
    fireEvent.click(screen.getByRole("button"));
    expect(handler).toHaveBeenCalledOnce();
  });
});

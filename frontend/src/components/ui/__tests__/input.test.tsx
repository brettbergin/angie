import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createRef } from "react";
import { Input } from "../input";

describe("Input", () => {
  it("renders with label when provided", () => {
    render(<Input label="Email" />);
    expect(screen.getByText("Email")).toBeInTheDocument();
  });

  it("renders without label when omitted", () => {
    const { container } = render(<Input placeholder="Type..." />);
    expect(container.querySelector("label")).toBeNull();
  });

  it("shows error message when error prop set", () => {
    render(<Input error="Required" />);
    expect(screen.getByText("Required")).toBeInTheDocument();
  });

  it("applies error border styling when error prop set", () => {
    render(<Input error="Bad" />);
    const input = screen.getByRole("textbox");
    expect(input.className).toContain("border-red-500");
  });

  it("forwards ref to input element", () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });
});

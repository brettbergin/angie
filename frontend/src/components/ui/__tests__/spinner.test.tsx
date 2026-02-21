import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Spinner } from "../spinner";

describe("Spinner", () => {
  it("renders with animate-spin class", () => {
    const { container } = render(<Spinner />);
    expect(container.firstElementChild!.className).toContain("animate-spin");
  });
});

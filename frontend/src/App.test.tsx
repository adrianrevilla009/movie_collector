import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], next_cursor: null }),
      }),
    );
  });

  it("renders the nav bar brand without crashing", async () => {
    render(<App />);
    const matches = await screen.findAllByText(
      (_, element) => element?.textContent === "CINEPLATFORM",
    );
    expect(matches.length).toBeGreaterThan(0);
  });
});

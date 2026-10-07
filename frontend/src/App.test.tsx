import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";

const signal = {
  product_id: "P001",
  product_name: "Orion X Pro",
  category: "Smartphones",
  brand: "Orion",
  market: "US",
  currency: "USD",
  observed_at: "2026-10-06T13:00:00Z",
  competitor_count: 4,
  avg_competitor_price: 999,
  min_competitor_price: 950,
  max_competitor_price: 1050,
  price_spread: 100,
  price_spread_pct: 10.01,
  lowest_competitor_name: "Northstar Retail",
  lowest_competitor_price: 950,
  highest_competitor_name: "Value Circuit",
  highest_competitor_price: 1050,
  in_stock_pct: 75,
  promotion_competitor_pct: 25,
  market_price_pressure: 0.1001,
  promotion_activity_flag: true,
};

const earlierSignal = {
  ...signal,
  observed_at: "2026-10-06T12:00:00Z",
  avg_competitor_price: 985,
  min_competitor_price: 940,
  max_competitor_price: 1030,
};

const alert = {
  product_id: "P001",
  product_name: "Orion X Pro",
  market: "US",
  currency: "USD",
  observed_at: "2026-10-06T13:00:00Z",
  signal_type: "PROMOTION_SURGE",
  severity: "LOW",
  message: "Competitors promoting increased from 0.00% to 25.00%.",
};

describe("MarketPulse dashboard", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = new URL(String(input));
        let body: unknown = [];
        if (url.pathname === "/products") {
          body = [
            {
              product_id: "P001",
              product_name: "Orion X Pro",
              category: "Smartphones",
              brand: "Orion",
            },
          ];
        } else if (url.pathname === "/market-signals") {
          body = [signal, earlierSignal];
        } else if (url.pathname === "/alerts") {
          body = [alert];
        } else if (url.pathname === "/alerts/summary") {
          body = {
            total_alerts: 1,
            counts: [
              {
                signal_type: "PROMOTION_SURGE",
                severity: "LOW",
                alert_count: 1,
              },
            ],
          };
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(body),
        } as Response);
      }),
    );
  });

  it("renders mocked API metrics, trend panels, product details, and alerts", async () => {
    render(<App />);

    expect(await screen.findByText("Competitive Intelligence")).toBeInTheDocument();
    expect(await screen.findByText("API connected")).toBeInTheDocument();
    expect(screen.getAllByText("$999.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Competitive price trend")).toBeInTheDocument();
    expect(screen.getByText("Inventory vs promotion")).toBeInTheDocument();
    expect(
      screen.getByText("Competitors promoting increased from 0.00% to 25.00%."),
    ).toBeInTheDocument();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(4));
  });

  it("requests server-side data again when a product filter changes", async () => {
    render(<App />);
    await screen.findByText("API connected");

    fireEvent.change(screen.getByRole("combobox", { name: "Product" }), {
      target: { value: "P001" },
    });

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(8));
    const requestedUrls = vi
      .mocked(fetch)
      .mock.calls.map(([input]) => String(input));
    expect(
      requestedUrls.some(
        (url) =>
          url.includes("/market-signals?") && url.includes("product_id=P001"),
      ),
    ).toBe(true);
    expect(
      requestedUrls.some(
        (url) => url.includes("/alerts?") && url.includes("product_id=P001"),
      ),
    ).toBe(true);

    fireEvent.click(screen.getAllByRole("button", { name: "Clear all" })[0]);
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(12));
    expect(
      (screen.getByRole("combobox", { name: "Product" }) as HTMLSelectElement).value,
    ).toBe("");
  });

  it("opens product intelligence and closes the drawer with Escape", async () => {
    render(<App />);
    await screen.findByText("API connected");

    fireEvent.click(screen.getByRole("button", { name: "Orion X Pro" }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Recent history")).toBeInTheDocument();
    expect(screen.getByText("Northstar Retail")).toBeInTheDocument();
    expect(screen.getByText(/Previous/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Orion X Pro" }).closest("tr"),
    ).toHaveClass("selected-row");

    fireEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: /PROMOTION SURGE/,
      }),
    );
    expect(screen.getByRole("heading", { name: "Signal details" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("opens an alert drawer and closes it from the close control", async () => {
    render(<App />);
    await screen.findByText("API connected");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Open LOW PROMOTION SURGE alert for Orion X Pro",
      }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("What changed")).toBeInTheDocument();
    expect(screen.getByText("Latest matching snapshot")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close details" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows exact chart values when a point is hovered", async () => {
    const { container } = render(<App />);
    await screen.findByText("API connected");

    const point = container.querySelector(".chart-point");
    expect(point).not.toBeNull();
    fireEvent.mouseEnter(point!);

    await waitFor(() =>
      expect(container.querySelector(".chart-tooltip")).toHaveTextContent(
        "Products in mean",
      ),
    );
  });
});

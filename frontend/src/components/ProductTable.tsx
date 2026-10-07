import { useMemo, useState } from "react";
import { formatCurrency, formatDateTime, formatPercent } from "../format";
import type { MarketSignal } from "../types";
import { Panel } from "./Panel";

type SortKey =
  | "product_name"
  | "category"
  | "brand"
  | "market"
  | "avg_competitor_price"
  | "price_spread_pct"
  | "in_stock_pct"
  | "promotion_competitor_pct"
  | "observed_at";

function latestByProductMarket(rows: MarketSignal[]): MarketSignal[] {
  const latest = new Map<string, MarketSignal>();
  for (const row of rows) {
    const key = `${row.product_id}:${row.market}:${row.currency}`;
    const existing = latest.get(key);
    if (!existing || Date.parse(row.observed_at) > Date.parse(existing.observed_at)) {
      latest.set(key, row);
    }
  }
  return [...latest.values()];
}

interface ProductTableProps {
  rows: MarketSignal[];
  selectedProductId: string;
  selectedMarket?: string;
  onSelectProduct: (productId: string) => void;
}

export function ProductTable({
  rows,
  selectedProductId,
  selectedMarket = "",
  onSelectProduct,
}: ProductTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("observed_at");
  const [ascending, setAscending] = useState(false);
  const latest = useMemo(() => latestByProductMarket(rows), [rows]);
  const sorted = [...latest].sort((left, right) => {
    const leftValue = left[sortKey];
    const rightValue = right[sortKey];
    const comparison =
      typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue));
    return ascending ? comparison : -comparison;
  });

  function sortBy(key: SortKey) {
    if (sortKey === key) setAscending(!ascending);
    else {
      setSortKey(key);
      setAscending(true);
    }
  }

  function heading(label: string, key: SortKey) {
    return (
      <button
        className="sort-button"
        type="button"
        onClick={() => sortBy(key)}
        aria-label={`Sort by ${label}`}
      >
        {label}
        <span aria-hidden="true">{sortKey === key ? (ascending ? " ↑" : " ↓") : ""}</span>
      </button>
    );
  }

  return (
    <Panel
      title="Product intelligence"
      eyebrow="Latest snapshot by product & market"
      action={<span className="panel-note">{latest.length} rows</span>}
      className="table-panel"
    >
      {sorted.length === 0 ? (
        <div className="empty-state">No product snapshots match these filters.</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{heading("Product", "product_name")}</th>
                <th>{heading("Category", "category")}</th>
                <th>{heading("Brand", "brand")}</th>
                <th>{heading("Market", "market")}</th>
                <th className="numeric">{heading("Avg price", "avg_competitor_price")}</th>
                <th className="numeric">{heading("Spread", "price_spread_pct")}</th>
                <th className="numeric">{heading("In stock", "in_stock_pct")}</th>
                <th className="numeric">{heading("Promotion", "promotion_competitor_pct")}</th>
                <th>{heading("Updated", "observed_at")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr
                  className={
                    row.product_id === selectedProductId &&
                    (!selectedMarket || row.market === selectedMarket)
                      ? "selected-row"
                      : ""
                  }
                  key={`${row.product_id}-${row.market}-${row.currency}`}
                >
                  <td>
                    <button
                      className="product-link"
                      type="button"
                      onClick={() => onSelectProduct(row.product_id)}
                    >
                      {row.product_name}
                    </button>
                    <small>{row.product_id}</small>
                  </td>
                  <td>{row.category}</td>
                  <td>{row.brand}</td>
                  <td>{row.market}</td>
                  <td className="numeric">
                    {formatCurrency(row.avg_competitor_price, row.currency)}
                  </td>
                  <td className="numeric">{formatPercent(row.price_spread_pct)}</td>
                  <td className="numeric">{formatPercent(row.in_stock_pct)}</td>
                  <td className="numeric">
                    {formatPercent(row.promotion_competitor_pct)}
                  </td>
                  <td className="muted-cell">{formatDateTime(row.observed_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

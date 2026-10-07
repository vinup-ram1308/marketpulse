import type { ChangeEvent, ReactNode } from "react";
import type { DashboardFilters, Product, SignalType, Severity } from "../types";

interface FilterBarProps {
  filters: DashboardFilters;
  products: Product[];
  markets: string[];
  onChange: (key: keyof DashboardFilters, value: string) => void;
  onReset: () => void;
  loading: boolean;
}

const SIGNAL_TYPES: SignalType[] = [
  "PRICE_MOVEMENT",
  "PROMOTION_SURGE",
  "INVENTORY_PRESSURE",
  "PRICE_DISPERSION",
];
const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH"];

function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="filter-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function FilterBar({
  filters,
  products,
  markets,
  onChange,
  onReset,
  loading,
}: FilterBarProps) {
  const handle =
    (key: keyof DashboardFilters) =>
    (event: ChangeEvent<HTMLSelectElement | HTMLInputElement>) =>
      onChange(key, event.target.value);

  return (
    <section className="filter-bar" aria-label="Dashboard filters" aria-busy={loading}>
      <div className="filter-heading">
        <span className="filter-heading-label">Refine view</span>
        {Object.values(filters).filter(Boolean).length > 0 && (
          <span className="active-filter-count">
            {Object.values(filters).filter(Boolean).length} active
          </span>
        )}
      </div>
      <div className="filter-controls">
      <Field label="Product">
        <select aria-label="Product" value={filters.product_id} onChange={handle("product_id")}>
          <option value="">All products</option>
          {products.map((product) => (
            <option key={product.product_id} value={product.product_id}>
              {product.product_name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Market">
        <select aria-label="Market" value={filters.market} onChange={handle("market")}>
          <option value="">All markets</option>
          {markets.map((market) => (
            <option key={market} value={market}>
              {market}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Signal">
        <select aria-label="Signal" value={filters.signal_type} onChange={handle("signal_type")}>
          <option value="">All signals</option>
          {SIGNAL_TYPES.map((signal) => (
            <option key={signal} value={signal}>
              {signal.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Severity">
        <select aria-label="Severity" value={filters.severity} onChange={handle("severity")}>
          <option value="">All severities</option>
          {SEVERITIES.map((severity) => (
            <option key={severity} value={severity}>
              {severity}
            </option>
          ))}
        </select>
      </Field>
      <Field label="From">
        <input
          aria-label="From"
          type="datetime-local"
          value={filters.start_time}
          onChange={handle("start_time")}
        />
      </Field>
      <Field label="To">
        <input
          aria-label="To"
          type="datetime-local"
          value={filters.end_time}
          onChange={handle("end_time")}
        />
      </Field>
      <button
        className="reset-button"
        type="button"
        onClick={onReset}
        disabled={Object.values(filters).every((value) => !value)}
      >
        Clear all
      </button>
      </div>
    </section>
  );
}

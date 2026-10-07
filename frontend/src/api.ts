import type {
  Alert,
  AlertCount,
  AlertSummary,
  DashboardFilters,
  MarketSignal,
  Product,
} from "./types";
import { SEVERITIES, SIGNAL_TYPES } from "./types";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isProduct(value: unknown): value is Product {
  return (
    isRecord(value) &&
    typeof value.product_id === "string" &&
    typeof value.product_name === "string" &&
    typeof value.category === "string" &&
    typeof value.brand === "string"
  );
}

function isMarketSignal(value: unknown): value is MarketSignal {
  return (
    isRecord(value) &&
    typeof value.product_id === "string" &&
    typeof value.product_name === "string" &&
    typeof value.category === "string" &&
    typeof value.brand === "string" &&
    typeof value.market === "string" &&
    typeof value.currency === "string" &&
    /^[A-Z]{3}$/.test(value.currency) &&
    typeof value.observed_at === "string" &&
    Number.isFinite(Date.parse(value.observed_at)) &&
    typeof value.competitor_count === "number" &&
    typeof value.avg_competitor_price === "number" &&
    typeof value.min_competitor_price === "number" &&
    typeof value.max_competitor_price === "number" &&
    typeof value.price_spread === "number" &&
    typeof value.price_spread_pct === "number" &&
    typeof value.lowest_competitor_name === "string" &&
    typeof value.lowest_competitor_price === "number" &&
    typeof value.highest_competitor_name === "string" &&
    typeof value.highest_competitor_price === "number" &&
    typeof value.in_stock_pct === "number" &&
    typeof value.promotion_competitor_pct === "number" &&
    typeof value.market_price_pressure === "number" &&
    typeof value.promotion_activity_flag === "boolean"
  );
}

function isAlert(value: unknown): value is Alert {
  return (
    isRecord(value) &&
    typeof value.product_id === "string" &&
    typeof value.product_name === "string" &&
    typeof value.market === "string" &&
    typeof value.currency === "string" &&
    /^[A-Z]{3}$/.test(value.currency) &&
    typeof value.observed_at === "string" &&
    Number.isFinite(Date.parse(value.observed_at)) &&
    typeof value.signal_type === "string" &&
    SIGNAL_TYPES.some((signalType) => signalType === value.signal_type) &&
    typeof value.severity === "string" &&
    SEVERITIES.some((severity) => severity === value.severity) &&
    typeof value.message === "string"
  );
}

function isAlertCount(value: unknown): value is AlertCount {
  return (
    isRecord(value) &&
    typeof value.signal_type === "string" &&
    SIGNAL_TYPES.some((signalType) => signalType === value.signal_type) &&
    typeof value.severity === "string" &&
    SEVERITIES.some((severity) => severity === value.severity) &&
    typeof value.alert_count === "number" &&
    Number.isInteger(value.alert_count) &&
    value.alert_count >= 0
  );
}

async function getJson<T>(
  path: string,
  parameters: URLSearchParams,
  signal: AbortSignal,
): Promise<T> {
  const query = parameters.toString();
  const response = await fetch(
    `${API_BASE_URL}${path}${query ? `?${query}` : ""}`,
    { headers: { Accept: "application/json" }, signal },
  );
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}).`);
  }
  return (await response.json()) as T;
}

function addParameter(
  parameters: URLSearchParams,
  name: string,
  value: string,
): void {
  if (value) parameters.set(name, value);
}

function timeParameter(value: string): string {
  return value ? new Date(value).toISOString() : "";
}

export async function fetchProducts(signal: AbortSignal): Promise<Product[]> {
  const result = await getJson<unknown>("/products", new URLSearchParams(), signal);
  if (!Array.isArray(result) || !result.every(isProduct)) {
    throw new Error("Products response was malformed.");
  }
  return result as Product[];
}

export async function fetchMarketSignals(
  filters: DashboardFilters,
  signal: AbortSignal,
): Promise<MarketSignal[]> {
  const parameters = new URLSearchParams({ limit: "100" });
  addParameter(parameters, "product_id", filters.product_id);
  addParameter(parameters, "market", filters.market);
  addParameter(parameters, "start_time", timeParameter(filters.start_time));
  addParameter(parameters, "end_time", timeParameter(filters.end_time));
  const result = await getJson<unknown>("/market-signals", parameters, signal);
  if (!Array.isArray(result) || !result.every(isMarketSignal)) {
    throw new Error("Market signals response was malformed.");
  }
  return result as MarketSignal[];
}

export async function fetchAlerts(
  filters: DashboardFilters,
  signal: AbortSignal,
): Promise<Alert[]> {
  const parameters = new URLSearchParams({ limit: "100" });
  addParameter(parameters, "product_id", filters.product_id);
  addParameter(parameters, "market", filters.market);
  addParameter(parameters, "signal_type", filters.signal_type);
  addParameter(parameters, "severity", filters.severity);
  addParameter(parameters, "start_time", timeParameter(filters.start_time));
  addParameter(parameters, "end_time", timeParameter(filters.end_time));
  const result = await getJson<unknown>("/alerts", parameters, signal);
  if (!Array.isArray(result) || !result.every(isAlert)) {
    throw new Error("Alerts response was malformed.");
  }
  return result as Alert[];
}

export async function fetchAlertSummary(
  signal: AbortSignal,
): Promise<AlertSummary> {
  const result = await getJson<unknown>(
    "/alerts/summary",
    new URLSearchParams(),
    signal,
  );
  if (
    typeof result !== "object" ||
    result === null ||
    !("total_alerts" in result) ||
    !("counts" in result) ||
    typeof result.total_alerts !== "number" ||
    !Number.isInteger(result.total_alerts) ||
    result.total_alerts < 0 ||
    !Array.isArray(result.counts) ||
    !result.counts.every(isAlertCount)
  ) {
    throw new Error("Alert summary response was malformed.");
  }
  return result as AlertSummary;
}

export type SignalType =
  | "PRICE_MOVEMENT"
  | "PROMOTION_SURGE"
  | "INVENTORY_PRESSURE"
  | "PRICE_DISPERSION";

export type Severity = "LOW" | "MEDIUM" | "HIGH";

export interface Product {
  product_id: string;
  product_name: string;
  category: string;
  brand: string;
}

export interface MarketSignal {
  product_id: string;
  product_name: string;
  category: string;
  brand: string;
  market: string;
  currency: string;
  observed_at: string;
  competitor_count: number;
  avg_competitor_price: number;
  min_competitor_price: number;
  max_competitor_price: number;
  price_spread: number;
  price_spread_pct: number;
  lowest_competitor_name: string;
  lowest_competitor_price: number;
  highest_competitor_name: string;
  highest_competitor_price: number;
  in_stock_pct: number;
  promotion_competitor_pct: number;
  market_price_pressure: number;
  promotion_activity_flag: boolean;
}

export interface Alert {
  product_id: string;
  product_name: string;
  market: string;
  currency: string;
  observed_at: string;
  signal_type: SignalType;
  severity: Severity;
  message: string;
}

export interface AlertCount {
  signal_type: SignalType;
  severity: Severity;
  alert_count: number;
}

export interface AlertSummary {
  total_alerts: number;
  counts: AlertCount[];
}

export interface DashboardFilters {
  product_id: string;
  market: string;
  signal_type: string;
  severity: string;
  start_time: string;
  end_time: string;
}

export const SIGNAL_TYPES: SignalType[] = [
  "PRICE_MOVEMENT",
  "PROMOTION_SURGE",
  "INVENTORY_PRESSURE",
  "PRICE_DISPERSION",
];

export const SEVERITIES: Severity[] = ["LOW", "MEDIUM", "HIGH"];

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchAlertSummary,
  fetchAlerts,
  fetchMarketSignals,
  fetchProducts,
} from "./api";

import { AlertTable } from "./components/AlertTable";
import { DetailDrawer } from "./components/DetailDrawer";
import { FilterBar } from "./components/FilterBar";
import {
  InventoryPromotionTrend,
  PriceTrend,
} from "./components/MarketCharts";
import { ProductDetail } from "./components/ProductDetail";
import { ProductTable } from "./components/ProductTable";

import {
  formatCurrency,
  formatDateTime,
  formatPercent,
  formatUtcDateTime,
} from "./format";

import type {
  Alert,
  AlertSummary,
  DashboardFilters,
  MarketSignal,
  Product,
} from "./types";

const INITIAL_FILTERS: DashboardFilters = {
  product_id: "",
  market: "",
  signal_type: "",
  severity: "",
  start_time: "",
  end_time: "",
};

const EMPTY_SUMMARY: AlertSummary = {
  total_alerts: 0,
  counts: [],
};

interface DashboardData {
  products: Product[];
  signals: MarketSignal[];
  alerts: Alert[];
  summary: AlertSummary;
}

const EMPTY_DATA: DashboardData = {
  products: [],
  signals: [],
  alerts: [],
  summary: EMPTY_SUMMARY,
};

const SECTIONS = [
  { id: "overview", label: "Overview", number: "01" },
  { id: "signals", label: "Signals", number: "02" },
  { id: "alerts", label: "Alerts", number: "03" },
  { id: "products", label: "Products", number: "04" },
] as const;

const SIGNAL_TYPES = [
  {
    type: "PROMOTION_SURGE",
    label: "Promotion",
    number: "01",
  },
  {
    type: "INVENTORY_PRESSURE",
    label: "Inventory",
    number: "02",
  },
  {
    type: "PRICE_MOVEMENT",
    label: "Price",
    number: "03",
  },
  {
    type: "PRICE_DISPERSION",
    label: "Dispersion",
    number: "04",
  },
] as const;

function mean(values: number[]): number | null {
  if (values.length === 0) return null;

  return (
    values.reduce((sum, value) => sum + value, 0) / values.length
  );
}

function signalLabel(signalType: string): string {
  return signalType.replaceAll("_", " ");
}

function signalChangeSummary(signalType: string): string {
  switch (signalType) {
    case "PROMOTION_SURGE":
      return "Promotion share shifted";
    case "INVENTORY_PRESSURE":
      return "Availability shifted";
    case "PRICE_MOVEMENT":
      return "Competitive price moved";
    case "PRICE_DISPERSION":
      return "Price dispersion widened";
    default:
      return "Market signal changed";
  }
}

function latestByTimestamp(rows: MarketSignal[]): MarketSignal | null {
  return (
    [...rows].sort(
      (left, right) =>
        Date.parse(right.observed_at) - Date.parse(left.observed_at),
    )[0] ?? null
  );
}

function getLatestSnapshotForProduct(
  rows: MarketSignal[],
  productId: string,
): MarketSignal | null {
  return latestByTimestamp(
    rows.filter((row) => row.product_id === productId),
  );
}

function formatAlertCount(count: number): string {
  return count.toString().padStart(2, "0");
}

function getSignalCount(
  summary: AlertSummary,
  signalType: string,
): number {
  return summary.counts
    .filter((row) => row.signal_type === signalType)
    .reduce((sum, row) => sum + row.alert_count, 0);
}

function getSignalAlertCount(
  alerts: Alert[],
  signalType: string,
): number {
  return alerts.filter((alert) => alert.signal_type === signalType).length;
}

function getHighSeverityCount(summary: AlertSummary): number {
  return summary.counts
    .filter((row) => row.severity === "HIGH")
    .reduce((sum, row) => sum + row.alert_count, 0);
}

function getLatestAlertForProduct(
  alerts: Alert[],
  productId: string,
): Alert | null {
  return (
    [...alerts]
      .filter((alert) => alert.product_id === productId)
      .sort(
        (left, right) =>
          Date.parse(right.observed_at) -
          Date.parse(left.observed_at),
      )[0] ?? null
  );
}

function App() {
  const [filters, setFilters] =
    useState<DashboardFilters>(INITIAL_FILTERS);

  const [data, setData] =
    useState<DashboardData>(EMPTY_DATA);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);

  const [selectedProduct, setSelectedProduct] =
    useState<MarketSignal | null>(null);

  const [selectedAlert, setSelectedAlert] =
    useState<Alert | null>(null);

  const [activeSection, setActiveSection] =
    useState<string>("overview");

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError("");

    Promise.all([
      fetchProducts(controller.signal),
      fetchMarketSignals(filters, controller.signal),
      fetchAlerts(filters, controller.signal),
      fetchAlertSummary(controller.signal),
    ])
      .then(([products, signals, alerts, summary]) => {
        setData({
          products,
          signals,
          alerts,
          summary,
        });
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;

        setError(
          requestError instanceof Error
            ? requestError.message
            : "Unable to load MarketPulse data.",
        );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [filters, refreshVersion]);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort(
            (left, right) =>
              left.boundingClientRect.top -
              right.boundingClientRect.top,
          );

        if (visible[0]) {
          setActiveSection(visible[0].target.id);
        }
      },
      {
        rootMargin: "-18% 0px -68% 0px",
        threshold: 0,
      },
    );

    for (const section of SECTIONS) {
      const element = document.getElementById(section.id);

      if (element) {
        observer.observe(element);
      }
    }

    return () => observer.disconnect();
  }, []);

  const markets = useMemo(
    () =>
      [...new Set(data.signals.map((row) => row.market))].sort(),
    [data.signals],
  );

  const latestDataTime = useMemo(
    () =>
      data.signals.reduce<string | null>((latest, row) => {
        if (
          !latest ||
          Date.parse(row.observed_at) > Date.parse(latest)
        ) {
          return row.observed_at;
        }

        return latest;
      }, null),
    [data.signals],
  );

  const activeFilterCount = Object.values(filters).filter(
    Boolean,
  ).length;

  const hasData =
    data.products.length > 0 ||
    data.signals.length > 0 ||
    data.alerts.length > 0;

  const currencies = useMemo(
    () =>
      [...new Set(data.signals.map((row) => row.currency))].sort(),
    [data.signals],
  );

  const averagePrice = useMemo(
    () =>
      mean(
        data.signals.map(
          (row) => row.avg_competitor_price,
        ),
      ),
    [data.signals],
  );

  const averageStock = useMemo(
    () =>
      mean(
        data.signals.map(
          (row) => row.in_stock_pct,
        ),
      ),
    [data.signals],
  );

  const averagePromotion = useMemo(
    () =>
      mean(
        data.signals.map(
          (row) => row.promotion_competitor_pct,
        ),
      ),
    [data.signals],
  );

  const highSeverityCount =
    getHighSeverityCount(data.summary);

  const latestAlerts = useMemo(
    () =>
      [...data.alerts].sort(
        (left, right) =>
          Date.parse(right.observed_at) -
          Date.parse(left.observed_at),
      ),
    [data.alerts],
  );

  const watchlistProducts = useMemo(() => {
    const seen = new Set<string>();

    const rows = [...data.signals].sort(
      (left, right) =>
        Date.parse(right.observed_at) -
        Date.parse(left.observed_at),
    );

    const result: MarketSignal[] = [];

    for (const row of rows) {
      const key = `${row.product_id}|${row.market}|${row.currency}`;

      if (seen.has(key)) continue;

      seen.add(key);
      result.push(row);

      if (result.length >= 6) break;
    }

    return result;
  }, [data.signals]);

  const marketHealthLabel =
    highSeverityCount === 0
      ? "Stable"
      : highSeverityCount <= 2
        ? "Watch"
        : "At risk";

  const marketHealthDetail =
    highSeverityCount === 0
      ? "No high-severity alerts currently recorded."
      : `${highSeverityCount} high-severity alert${
          highSeverityCount === 1 ? "" : "s"
        } require attention.`;

  const alertContext = selectedAlert
    ? getLatestSnapshotForProduct(
        data.signals,
        selectedAlert.product_id,
      )
    : null;

  function updateFilter(
    key: keyof DashboardFilters,
    value: string,
  ) {
    setFilters((current) => {
      if (current[key] === value) return current;

      return {
        ...current,
        [key]: value,
      };
    });

    if (key === "product_id") {
      setSelectedProduct(null);
      setSelectedAlert(null);
    }

    if (key === "signal_type" || key === "severity") {
      setSelectedAlert(null);
    }
  }

  function resetFilters() {
    setFilters({ ...INITIAL_FILTERS });
  }

  const closeDrawer = useCallback(() => {
    setSelectedAlert(null);
    setSelectedProduct(null);
  }, []);

  function navigateTo(sectionId: string) {
    setActiveSection(sectionId);

    requestAnimationFrame(() => {
      const section = document.getElementById(sectionId);

      if (!section) return;

      const top =
        section.getBoundingClientRect().top +
        window.scrollY -
        84;

      window.scrollTo({
        top,
        behavior: "smooth",
      });
    });
  }

    function openSignalAlerts(signalType: string) {
      setFilters((current) => ({
        ...current,
        signal_type: signalType,
      }));

      setSelectedAlert(null);
      setSelectedProduct(null);

      navigateTo("alerts");
    }

  function selectAlert(alert: Alert) {
    setSelectedProduct(null);
    setSelectedAlert(alert);
  }

  function selectProduct(productId: string) {
    const row =
      data.signals.find(
        (signal) => signal.product_id === productId,
      ) ?? null;

    if (!row) return;

    setSelectedAlert(null);
    setSelectedProduct(row);
  }

  return (
    <div className="app-shell marketpulse-v2">
      <aside
        className="nav-rail"
        aria-label="Primary navigation"
      >
        <div className="rail-top">
          <a
            className="rail-brand"
            href="#overview"
            aria-label="MarketPulse overview"
            onClick={(event) => {
              event.preventDefault();
              navigateTo("overview");
            }}
          >
            <span
              className="brand-mark"
              aria-hidden="true"
            >
              <i />
              <i />
              <i />
            </span>

            <span className="rail-brand-name">
              MARKETPULSE
            </span>
          </a>

          <span className="rail-caption">
            Competitive Intelligence
          </span>
        </div>

        <nav className="rail-nav">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              className={`rail-link ${
                activeSection === section.id
                  ? "is-active"
                  : ""
              }`}
              href={`#${section.id}`}
              aria-current={
                activeSection === section.id
                  ? "page"
                  : undefined
              }
              onClick={(event) => {
                event.preventDefault();
                navigateTo(section.id);
              }}
            >
              <span className="rail-number">
                {section.number}
              </span>

              <span>{section.label}</span>
            </a>
          ))}
        </nav>

        <div className="rail-context">
          <div className="rail-context-label">
            WORKSPACE
          </div>

          <div className="rail-context-value">
            {filters.market || "All markets"}
          </div>

          <div className="rail-context-meta">
            {markets.length || 0} market
            {markets.length === 1 ? "" : "s"}
          </div>
        </div>

        <div className="rail-footer">
          <span className="live-dot" />
          <span>LIVE FEED</span>
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <div className="topbar-breadcrumb">
            <span>MARKETPULSE</span>
            <span
              className="breadcrumb-slash"
              aria-hidden="true"
            >
              /
            </span>
            <span>
              {activeSection.toUpperCase()}
            </span>
          </div>

          <div className="header-meta">
            <div className="data-clock">
              <span>LATEST OBSERVATION</span>

              <strong>
                {formatUtcDateTime(latestDataTime)}
              </strong>
            </div>

            <div
              className={`connection-state ${
                error
                  ? "offline"
                  : loading
                    ? "connecting"
                    : "online"
              }`}
              role="status"
            >
              <i />

              {error
                ? "API unavailable"
                : loading
                  ? "Updating"
                  : "API connected"}
            </div>

            <button
              className="refresh-button"
              type="button"
              onClick={() =>
                setRefreshVersion(
                  (version) => version + 1,
                )
              }
              disabled={loading}
              aria-label={
                loading
                  ? "Refreshing market data"
                  : "Refresh market data"
              }
            >
              <span aria-hidden="true">↻</span>
              <span>REFRESH</span>
            </button>
          </div>
        </header>

        <main
          className="dashboard"
          aria-busy={loading}
        >
          <section
            id="overview"
            className="market-hero"
          >
            <div className="hero-main">
              <div className="hero-kicker">
                LIVE MARKET INTELLIGENCE
              </div>

              <h1>
                Competitive
                <br />
                market watch
              </h1>

              <p>
                Pricing, availability, and promotion
                shifts across observed markets.
              </p>

              <div className="hero-context">
                <span className="context-item">
                  <span className="context-label">
                    MARKET
                  </span>
                  <strong>
                    {filters.market ||
                      "All observed markets"}
                  </strong>
                </span>

                <span className="context-item">
                  <span className="context-label">
                    PRODUCTS
                  </span>
                  <strong>
                    {data.products.length}
                  </strong>
                </span>

                <span className="context-item">
                  <span className="context-label">
                    SNAPSHOTS
                  </span>
                  <strong>
                    {data.signals.length}
                  </strong>
                </span>
              </div>
            </div>

            <aside className="market-snapshot">
              <div className="snapshot-label">
                MARKET HEALTH
              </div>

              <div className="snapshot-health">
                <span className="health-dot" />
                <strong>{marketHealthLabel}</strong>
              </div>

              <p>{marketHealthDetail}</p>

              <div className="snapshot-metrics">
                <div>
                  <span>Alerts</span>
                  <strong>
                    {data.summary.total_alerts}
                  </strong>
                </div>

                <div>
                  <span>High</span>
                  <strong>
                    {highSeverityCount}
                  </strong>
                </div>

                <div>
                  <span>Currencies</span>
                  <strong>
                    {currencies.length}
                  </strong>
                </div>
              </div>
            </aside>
          </section>

          <section
            className="control-zone"
            aria-label="Dashboard controls"
          >
            <FilterBar
              filters={filters}
              products={data.products}
              markets={markets}
              onChange={updateFilter}
              onReset={resetFilters}
              loading={loading}
            />

            <div
              className="control-summary"
              aria-live="polite"
            >
              <span>
                {data.signals.length} snapshots in view
              </span>

              {activeFilterCount > 0 && (
                <>
                  <span className="control-divider">
                    /
                  </span>

                  <span>
                    {activeFilterCount} active{" "}
                    {activeFilterCount === 1
                      ? "filter"
                      : "filters"}
                  </span>

                  <button
                    className="control-clear"
                    type="button"
                    onClick={resetFilters}
                  >
                    Clear all
                  </button>
                </>
              )}
            </div>
          </section>

          {error && (
            <div
              className="error-banner"
              role="alert"
            >
              <span className="error-mark">!</span>

              <span className="error-copy">
                <strong>
                  Market data could not be updated.
                </strong>{" "}
                {error} Existing results are preserved.
              </span>

              <button
                type="button"
                onClick={() =>
                  setRefreshVersion(
                    (version) => version + 1,
                  )
                }
                disabled={loading}
              >
                Retry
              </button>
            </div>
          )}

          {loading && hasData && (
            <div
              className="loading-line"
              role="status"
              aria-label="Updating market data"
            />
          )}

          <section
            className="metric-strip"
            aria-label="Market metrics"
          >
            <div className="metric-primary">
              <span className="metric-label">
                TOTAL ALERTS
              </span>

              <strong className="metric-value">
                {data.summary.total_alerts.toLocaleString()}
              </strong>

              <span className="metric-detail">
                Recorded across the current feed
              </span>
            </div>

            <div className="metric-primary metric-primary-accent">
              <span className="metric-label">
                PRODUCTS MONITORED
              </span>

              <strong className="metric-value">
                {data.products.length.toLocaleString()}
              </strong>

              <span className="metric-detail">
                Catalog items represented in the feed
              </span>
            </div>

            <div className="metric-support">
              <span className="metric-label">
                AVG COMPETITOR PRICE
              </span>

              <strong className="metric-support-value">
                {averagePrice !== null &&
                currencies.length === 1
                  ? formatCurrency(
                      averagePrice,
                      currencies[0],
                    )
                  : "—"}
              </strong>

              <span className="metric-detail">
                {currencies.length > 1
                  ? "Mixed currencies in view"
                  : "Mean of visible snapshots"}
              </span>
            </div>

            <div className="metric-support">
              <span className="metric-label">
                IN STOCK
              </span>

              <strong className="metric-support-value">
                {averageStock !== null
                  ? formatPercent(averageStock)
                  : "—"}
              </strong>

              <span className="metric-detail">
                Competitor availability mean
              </span>
            </div>

            <div className="metric-support">
              <span className="metric-label">
                PROMOTIONS
              </span>

              <strong className="metric-support-value">
                {averagePromotion !== null
                  ? formatPercent(
                      averagePromotion,
                    )
                  : "—"}
              </strong>

              <span className="metric-detail">
                Competitor promotion share
              </span>
            </div>
          </section>

          <section
            id="signals"
            className="signal-landscape"
            aria-label="Signal summary"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">
                  SIGNAL LANDSCAPE
                </p>

                <h2>What is moving</h2>

                <p className="section-copy">
                  The latest detected competitive
                  changes, grouped by signal family.
                </p>
              </div>

              <span className="section-meta">
                {data.alerts.length} active signal
                {data.alerts.length === 1
                  ? ""
                  : "s"}
              </span>
            </div>

            <div className="signal-board">
              {SIGNAL_TYPES.map((signal) => {
                const summaryCount =
                  getSignalCount(
                    data.summary,
                    signal.type,
                  );

                const visibleCount =
                  getSignalAlertCount(
                    data.alerts,
                    signal.type,
                  );

                const active =
                  filters.signal_type === signal.type;

                return (
                  <button
                    key={signal.type}
                    type="button"
                    className={`signal-card ${
                      active ? "is-selected" : ""
                    } ${
                      visibleCount > 0
                        ? "has-alerts"
                        : ""
                    }`}
                    aria-pressed={active}
                    onClick={() =>
                      openSignalAlerts(
                        signal.type,
                      )
                    }
                  >
                    <div className="signal-card-top">
                      <span className="signal-card-number">
                        {signal.number}
                      </span>

                      <span className="signal-card-count">
                        {formatAlertCount(
                          visibleCount,
                        )}
                      </span>
                    </div>

                    <div className="signal-card-title">
                      {signal.label}
                    </div>

                    <div className="signal-card-status">
                      {visibleCount > 0
                        ? "ACTIVE SIGNALS"
                        : summaryCount > 0
                          ? "IN RECENT HISTORY"
                          : "NO CURRENT SIGNALS"}
                    </div>

                    <div className="signal-card-footer">
                      <span>
                        {summaryCount} recorded
                      </span>

                      <span 
                      className="signal-card-arrow"
                      aria-hidden="true">
                        →
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section
            className="analytics-core"
            aria-label="Competitive analytics"
          >
            <div className="analytics-primary">
              <PriceTrend rows={data.signals} />
            </div>

            <aside className="analytics-side">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">
                    MARKET SNAPSHOT
                  </p>

                  <h2>Current position</h2>
                </div>
              </div>

              <div className="market-health-content">
                <div className="health-main">
                  <span className="health-main-label">
                    CURRENT HEALTH
                  </span>

                  <strong>
                    {marketHealthLabel}
                  </strong>

                  <p>{marketHealthDetail}</p>
                </div>

                <div className="health-stat-list">
                  <div className="health-stat">
                    <span>Avg price</span>

                    <strong>
                      {averagePrice !== null &&
                      currencies.length === 1
                        ? formatCurrency(
                            averagePrice,
                            currencies[0],
                          )
                        : "—"}
                    </strong>
                  </div>

                  <div className="health-stat">
                    <span>In stock</span>

                    <strong>
                      {averageStock !== null
                        ? formatPercent(
                            averageStock,
                          )
                        : "—"}
                    </strong>
                  </div>

                  <div className="health-stat">
                    <span>Promotions</span>

                    <strong>
                      {averagePromotion !== null
                        ? formatPercent(
                            averagePromotion,
                          )
                        : "—"}
                    </strong>
                  </div>

                  <div className="health-stat">
                    <span>High severity</span>

                    <strong>
                      {highSeverityCount}
                    </strong>
                  </div>
                </div>
              </div>
            </aside>
          </section>

          <section
            className="secondary-chart-section"
            aria-label="Inventory and promotion trends"
          >
            <InventoryPromotionTrend rows={data.signals} />
          </section>

          <section className="signal-watch-grid">
            <div className="signal-stream-section">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">
                    RECENT CHANGES
                  </p>

                  <h2>Signal stream</h2>
                </div>

                <button
                  className="text-link-button"
                  type="button"
                  onClick={() =>
                    navigateTo("alerts")
                  }
                >
                  View all
                  <span aria-hidden="true">
                    →
                  </span>
                </button>
              </div>

              <div className="signal-stream">
                {latestAlerts.length === 0 ? (
                  <div className="inline-empty">
                    <span
                      className="empty-mark"
                      aria-hidden="true"
                    >
                      —
                    </span>

                    <strong>
                      No recent signals
                    </strong>

                    <span>
                      The stream will populate as
                      the pipeline detects
                      meaningful market changes.
                    </span>
                  </div>
                ) : (
                  latestAlerts
                    .slice(0, 6)
                    .map((alert) => (
                      <button
                        key={`${alert.product_id}|${alert.market}|${alert.currency}|${alert.observed_at}|${alert.signal_type}|${alert.severity}`}
                        className="stream-item"
                        type="button"
                        aria-label={`Open ${alert.severity} ${alert.signal_type} alert for ${alert.product_name}`}
                        onClick={() =>
                          selectAlert(alert)
                        }
                      >
                        <span
                          className={`stream-severity ${
                            alert.severity.toLowerCase()
                          }`}
                        >
                          {alert.severity}
                        </span>

                        <span className="stream-body">
                          <span className="stream-title">
                            {signalLabel(
                              alert.signal_type,
                            )}
                          </span>

                          <strong>
                            {alert.product_name}
                          </strong>

                          <span className="stream-message">
                            {signalChangeSummary(alert.signal_type)}
                          </span>
                        </span>

                        <span className="stream-time">
                          {formatDateTime(
                            alert.observed_at,
                          )}
                        </span>

                        <span
                          className="stream-action"
                          aria-hidden="true"
                        >
                          →
                        </span>
                      </button>
                    ))
                )}
              </div>
            </div>

            <aside className="product-watchlist">
              <div className="section-heading compact">
                <div>
                  <p className="eyebrow">
                    QUICK ACCESS
                  </p>

                  <h2>Product watchlist</h2>
                </div>

                <button
                  className="text-link-button"
                  type="button"
                  onClick={() =>
                    navigateTo("products")
                  }
                >
                  Browse
                  <span aria-hidden="true">
                    →
                  </span>
                </button>
              </div>

              <div className="watchlist">
                {watchlistProducts.length ===
                0 ? (
                  <div className="inline-empty">
                    <span
                      className="empty-mark"
                      aria-hidden="true"
                    >
                      —
                    </span>

                    <strong>
                      No products in view
                    </strong>

                    <span>
                      Product snapshots will
                      appear here once data is
                      available.
                    </span>
                  </div>
                ) : (
                  watchlistProducts.map(
                    (product) => {
                      const latestAlert =
                        getLatestAlertForProduct(
                          data.alerts,
                          product.product_id,
                        );

                      return (
                        <button
                          key={`${product.product_id}|${product.market}|${product.currency}`}
                          type="button"
                          className="watchlist-item"
                          onClick={() =>
                            selectProduct(
                              product.product_id,
                            )
                          }
                        >
                          <span className="watchlist-main">
                            <strong>
                              {product.product_name}
                            </strong>

                            <span>
                              {product.brand}{" "}
                              · {product.category}
                            </span>
                          </span>

                          <span className="watchlist-price">
                            {formatCurrency(
                              product.avg_competitor_price,
                              product.currency,
                            )}
                          </span>

                          <span className="watchlist-stock">
                            {formatPercent(
                              product.in_stock_pct,
                            )}
                          </span>

                          {latestAlert ? (
                            <span
                              className={`watchlist-alert ${
                                latestAlert.severity.toLowerCase()
                              }`}
                            >
                              {signalLabel(
                                latestAlert.signal_type,
                              )}
                            </span>
                          ) : (
                            <span className="watchlist-alert neutral">
                              No active alert
                            </span>
                          )}

                          <span
                            className="watchlist-action"
                            aria-hidden="true"
                          >
                            →
                          </span>
                        </button>
                      );
                    },
                  )
                )}
              </div>
            </aside>
          </section>

          <section
            id="alerts"
            className="content-section alerts-section"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">
                  INVESTIGATION QUEUE
                </p>

                <h2>Alerts</h2>

                <p className="section-copy">
                  Review the signal records behind
                  the current market picture.
                </p>
              </div>

              <span className="section-meta">
                {data.alerts.length} alerts
              </span>
            </div>

            <AlertTable
              alerts={data.alerts}
              onSelectAlert={selectAlert}
            />
          </section>

          <section
            id="products"
            className="content-section product-section"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">
                  PRODUCT INTELLIGENCE
                </p>

                <h2>Product watchlist</h2>

                <p className="section-copy">
                  Current competitive snapshots
                  across products and observed
                  markets.
                </p>
              </div>

              <span className="section-meta">
                {data.signals.length} snapshots
              </span>
            </div>

            <ProductTable
              rows={data.signals}
              selectedProductId={
                selectedProduct?.product_id ?? ""
              }
              selectedMarket={
                selectedProduct?.market
              }
              onSelectProduct={selectProduct}
            />
          </section>

          {!loading && !error && !hasData && (
            <section className="global-empty">
              <span
                className="empty-mark"
                aria-hidden="true"
              >
                —
              </span>

              <h2>No market data available</h2>

              <p>
                There are no snapshots or alerts to
                display. Refresh after the data
                pipeline has loaded observations.
              </p>

              <button
                className="refresh-button"
                type="button"
                onClick={() =>
                  setRefreshVersion(
                    (version) => version + 1,
                  )
                }
              >
                Retry connection
              </button>
            </section>
          )}

          <footer className="footer">
            <span>
              MarketPulse
              <span className="footer-separator">
                /
              </span>
              Competitive intelligence
            </span>

            <span>
              Data through{" "}
              {formatDateTime(latestDataTime)}
              <span className="footer-dot">
                ·
              </span>
              Curated market observations
            </span>
          </footer>
        </main>
      </div>

      {(selectedProduct || selectedAlert) && (
        <DetailDrawer
          title={
            selectedAlert
              ? "Signal details"
              : "Product intelligence"
          }
          eyebrow={
            selectedAlert
              ? "Alert investigation"
              : "Market position"
          }
          onClose={closeDrawer}
        >
          {selectedAlert ? (
            <div className="alert-detail">
              <div className="drawer-signal-heading">
                <span
                  className={`signal-tag signal-${selectedAlert.signal_type.toLowerCase()}`}
                >
                  {signalLabel(
                    selectedAlert.signal_type,
                  )}
                </span>

                <span
                  className={`severity-badge ${selectedAlert.severity.toLowerCase()}`}
                >
                  <i />
                  {selectedAlert.severity}
                </span>
              </div>

              <h3>
                {selectedAlert.product_name}
              </h3>

              <p className="drawer-subtitle">
                {selectedAlert.market} ·{" "}
                {selectedAlert.currency} ·{" "}
                {selectedAlert.product_id}
              </p>

              <time
                className="drawer-time"
                dateTime={selectedAlert.observed_at}
              >
                Observed{" "}
                {formatDateTime(
                  selectedAlert.observed_at,
                )}
              </time>

              <div className="alert-message-card">
                <span className="eyebrow">
                  What changed
                </span>

                <p>
                  {selectedAlert.message}
                </p>
              </div>

              {alertContext ? (
                <div className="drawer-context">
                  <h3>
                    Latest matching snapshot
                  </h3>

                  <p>
                    Context for{" "}
                    {alertContext.market} ·{" "}
                    {alertContext.currency}; values
                    are not necessarily from the
                    alert timestamp.
                  </p>

                  <div className="drawer-context-grid">
                    <div>
                      <span>
                        Average competitor price
                      </span>

                      <strong>
                        {formatCurrency(
                          alertContext.avg_competitor_price,
                          alertContext.currency,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Lowest competitor price
                      </span>

                      <strong>
                        {formatCurrency(
                          alertContext.lowest_competitor_price,
                          alertContext.currency,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Highest competitor price
                      </span>

                      <strong>
                        {formatCurrency(
                          alertContext.highest_competitor_price,
                          alertContext.currency,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>In stock</span>

                      <strong>
                        {formatPercent(
                          alertContext.in_stock_pct,
                        )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        Promotion share
                      </span>

                      <strong>
                        {formatPercent(
                          alertContext.promotion_competitor_pct,
                        )}
                      </strong>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="drawer-context-empty">
                  No matching product snapshot is
                  included in the current signal
                  result.
                </p>
              )}
            </div>
          ) : (
            <ProductDetail
              product={selectedProduct}
              alerts={data.alerts}
              history={data.signals}
              onSelectAlert={(alert) => {
                setSelectedProduct(null);
                setSelectedAlert(alert);
              }}
            />
          )}
        </DetailDrawer>
      )}
    </div>
  );
}

export default App;
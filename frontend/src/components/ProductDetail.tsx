import { formatCurrency, formatDateTime, formatPercent } from "../format";
import type { Alert, MarketSignal } from "../types";
import { LineChart, type ChartSeries } from "./LineChart";
import { Panel } from "./Panel";

interface ProductDetailProps {
  product: MarketSignal | null;
  alerts: Alert[];
  history: MarketSignal[];
  onSelectAlert: (alert: Alert) => void;
}

export function ProductDetail({
  product,
  alerts,
  history,
  onSelectAlert,
}: ProductDetailProps) {
  if (!product) {
    return (
      <Panel title="Product detail" eyebrow="Snapshot breakdown">
        <div className="empty-state">
          Select a product snapshot to inspect its competitive position.
        </div>
      </Panel>
    );
  }

  const trend = [...history]
    .filter(
      (row) =>
        row.product_id === product.product_id &&
        row.market === product.market &&
        row.currency === product.currency,
    )
    .sort((left, right) => Date.parse(left.observed_at) - Date.parse(right.observed_at));
  const previous = trend.length > 1 ? trend[trend.length - 2] : null;
  const priceChange =
    previous && previous.avg_competitor_price !== 0
      ? ((product.avg_competitor_price - previous.avg_competitor_price) /
          previous.avg_competitor_price) * 100
      : null;
  const related = alerts.filter(
    (alert) =>
      alert.product_id === product.product_id && alert.market === product.market,
  );
  const trendSeries: ChartSeries[] = [
    {
      label: `${product.market} · ${product.currency}`,
      color: "#2865c7",
      points: trend.map((row) => ({
        timestamp: row.observed_at,
        label: formatDateTime(row.observed_at),
        value: row.avg_competitor_price,
        details: [
          { label: "Lowest", value: formatCurrency(row.lowest_competitor_price, row.currency) },
          { label: "Highest", value: formatCurrency(row.highest_competitor_price, row.currency) },
          { label: "Spread", value: formatPercent(row.price_spread_pct) },
        ],
      })),
    },
  ];

  return (
    <Panel
      title={product.product_name}
      eyebrow={`Product detail · ${product.product_id} · ${product.market}`}
      action={<span className="panel-note">{product.currency}</span>}
    >
      <div className="detail-metrics">
        <div>
          <span>Average competitor price</span>
          <strong>{formatCurrency(product.avg_competitor_price, product.currency)}</strong>
        </div>
        <div>
          <span>Lowest competitor</span>
          <strong>{formatCurrency(product.min_competitor_price, product.currency)}</strong>
          <small>{product.lowest_competitor_name}</small>
        </div>
        <div>
          <span>Highest competitor</span>
          <strong>{formatCurrency(product.max_competitor_price, product.currency)}</strong>
          <small>{product.highest_competitor_name}</small>
        </div>
        <div>
          <span>Price spread</span>
          <strong>{formatCurrency(product.price_spread, product.currency)}</strong>
          <small>{formatPercent(product.price_spread_pct)} of average</small>
        </div>
        <div>
          <span>In stock</span>
          <strong>{formatPercent(product.in_stock_pct)}</strong>
        </div>
        <div>
          <span>Promotion share</span>
          <strong>{formatPercent(product.promotion_competitor_pct)}</strong>
        </div>
      </div>
      <div className="product-trend">
        <div className="product-trend-heading">
          <div>
            <span className="eyebrow">Recent history</span>
            <h3>Average competitor price</h3>
          </div>
          <span className="trend-change">
            {previous ? (
              <>
                Previous {formatCurrency(previous.avg_competitor_price, product.currency)}
                <strong className={priceChange === null ? "" : priceChange >= 0 ? "positive" : "negative"}>
                  {priceChange === null ? " —" : ` ${priceChange >= 0 ? "+" : ""}${priceChange.toFixed(2)}%`}
                </strong>
              </>
            ) : "No previous snapshot"}
          </span>
        </div>
        <LineChart
          series={trendSeries}
          chartLabel={`Recent ${product.market} ${product.currency} average price`}
          formatValue={(value) => formatCurrency(value, product.currency)}
          emptyMessage="A price trend needs more than one matching snapshot."
        />
      </div>
      <div className="detail-footer">
        <span>Current {formatCurrency(product.avg_competitor_price, product.currency)}</span>
        <span>Observed {formatDateTime(product.observed_at)}</span>
        <span>{related.length} related alert{related.length === 1 ? "" : "s"}</span>
      </div>
      <section className="related-alerts" aria-label="Related alerts">
        <header>
          <h3>Related alerts</h3>
          <span>{related.length}</span>
        </header>
        {related.length === 0 ? (
          <p className="related-alerts-empty">No related alerts in the current result.</p>
        ) : (
          <div>
            {related.map((alert, index) => (
              <button
                type="button"
                className="related-alert"
                key={`${alert.observed_at}-${alert.signal_type}-${index}`}
                onClick={() => onSelectAlert(alert)}
              >
                <span className={`severity-badge ${alert.severity.toLowerCase()}`}>
                  <i />{alert.severity}
                </span>
                <span className="related-alert-main">
                  <strong>{alert.signal_type.replaceAll("_", " ")}</strong>
                  <small>{alert.message}</small>
                </span>
                <time dateTime={alert.observed_at}>{formatDateTime(alert.observed_at)}</time>
              </button>
            ))}
          </div>
        )}
      </section>
    </Panel>
  );
}

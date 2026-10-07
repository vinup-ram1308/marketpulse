import { formatCurrency, formatPercent } from "../format";
import type { MarketSignal } from "../types";
import { LineChart, type ChartPoint, type ChartSeries } from "./LineChart";
import { Panel } from "./Panel";

function mean(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function timestampLabel(timestamp: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(new Date(timestamp));
}

function aggregateByTime(
  rows: MarketSignal[],
  select: (row: MarketSignal) => number,
): ChartPoint[] {
  const groups = new Map<string, MarketSignal[]>();
  for (const row of rows) {
    const snapshots = groups.get(row.observed_at) ?? [];
    snapshots.push(row);
    groups.set(row.observed_at, snapshots);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => Date.parse(left) - Date.parse(right))
    .map(([timestamp, snapshots]) => ({
      timestamp,
      label: timestampLabel(timestamp),
      value: mean(snapshots.map(select)),
      details: [{ label: "Snapshots in mean", value: String(snapshots.length) }],
    }));
}

function priceSeries(rows: MarketSignal[], currency: string, color: string): ChartSeries {
  const matchingRows = rows.filter((row) => row.currency === currency);
  const groups = new Map<string, MarketSignal[]>();
  for (const row of matchingRows) {
    const snapshots = groups.get(row.observed_at) ?? [];
    snapshots.push(row);
    groups.set(row.observed_at, snapshots);
  }
  const points = [...groups.entries()]
    .sort(([left], [right]) => Date.parse(left) - Date.parse(right))
    .map(([timestamp, snapshots]) => ({
      timestamp,
      label: timestampLabel(timestamp),
      value: mean(snapshots.map((row) => row.avg_competitor_price)),
      details: [
        {
          label: "Mean lowest price",
          value: formatCurrency(mean(snapshots.map((row) => row.lowest_competitor_price)), currency),
        },
        {
          label: "Mean highest price",
          value: formatCurrency(mean(snapshots.map((row) => row.highest_competitor_price)), currency),
        },
        {
          label: "Mean spread",
          value: formatPercent(mean(snapshots.map((row) => row.price_spread_pct))),
        },
        { label: "Products in mean", value: String(snapshots.length) },
      ],
    }));
  return { label: `${currency} average`, color, points };
}

export function PriceTrend({ rows }: { rows: MarketSignal[] }) {
  const currencies = [...new Set(rows.map((row) => row.currency))].sort();
  const colors = ["#2865c7", "#17816c", "#b87820", "#7659b4"];
  const series = currencies.map((currency, index) =>
    priceSeries(rows, currency, colors[index % colors.length]),
  );

  return (
    <Panel
      title="Competitive price trend"
      eyebrow="Market movement"
      action={<span className="panel-note">Mean by timestamp · currencies shown separately</span>}
    >
      {series.length > 1 ? (
        <div className="currency-charts">
          {series.map((item) => (
            <section className="currency-chart" key={item.label}>
              <h3>{item.label}</h3>
              <LineChart
                series={[item]}
                chartLabel={`${item.label} competitor price by timestamp`}
                formatValue={(value) => formatCurrency(value, item.label.slice(0, 3))}
                emptyMessage="No snapshots in this currency."
              />
            </section>
          ))}
        </div>
      ) : (
        <LineChart
          series={series}
          chartLabel="Average competitor price by timestamp"
          formatValue={(value) =>
            currencies.length === 1
              ? formatCurrency(value, currencies[0])
              : new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
          }
          emptyMessage="No market snapshots match this view. Adjust the filters to see a trend."
        />
      )}
    </Panel>
  );
}

export function InventoryPromotionTrend({ rows }: { rows: MarketSignal[] }) {
  const series: ChartSeries[] = [
    {
      label: "In stock",
      color: "#16816c",
      points: aggregateByTime(rows, (row) => row.in_stock_pct),
    },
    {
      label: "Promotion share",
      color: "#b87820",
      points: aggregateByTime(rows, (row) => row.promotion_competitor_pct),
    },
  ];

  return (
    <Panel
      title="Inventory vs promotion"
      eyebrow="Availability & activity"
      action={<span className="panel-note">Mean share by snapshot · %</span>}
    >
      <LineChart
        series={series}
        chartLabel="Mean competitor in-stock and promotion share by timestamp"
        formatValue={formatPercent}
        emptyMessage="No inventory or promotion snapshots match this view."
      />
    </Panel>
  );
}

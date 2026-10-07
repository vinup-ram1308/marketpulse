import { useMemo, useState } from "react";

export interface ChartPoint {
  label: string;
  value: number;
  timestamp?: string;
  details?: { label: string; value: string }[];
}

export interface ChartSeries {
  label: string;
  color: string;
  points: ChartPoint[];
}

interface LineChartProps {
  series: ChartSeries[];
  formatValue: (value: number) => string;
  emptyMessage: string;
  chartLabel?: string;
}

const WIDTH = 720;
const HEIGHT = 250;

const PADDING = {
  top: 24,
  right: 20,
  bottom: 38,
  left: 66,
};

function formatTimestamp(
  value: string | undefined,
  fallback: string,
): string {
  if (!value) return fallback;

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return fallback;
  }

  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    timeZoneName: "short",
  }).format(date);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function LineChart({
  series,
  formatValue,
  emptyMessage,
  chartLabel = "Time series chart",
}: LineChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);

  const visibleSeries = useMemo(
    () => series.filter((item) => !hiddenSeries.includes(item.label)),
    [series, hiddenSeries],
  );

  const pointCount = Math.max(
    ...visibleSeries.map((item) => item.points.length),
    0,
  );

  const points = useMemo(
    () => visibleSeries.flatMap((item) => item.points),
    [visibleSeries],
  );

  if (pointCount === 0 || points.length === 0) {
    return <div className="chart-empty">{emptyMessage}</div>;
  }

  const values = points
    .map((point) => point.value)
    .filter((value) => Number.isFinite(value));

  const rawMinimum = Math.min(...values);
  const rawMaximum = Math.max(...values);

  const rawRange =
    rawMaximum - rawMinimum ||
    Math.max(Math.abs(rawMaximum) * 0.08, 1);

  const padding = rawRange * 0.08;
  const minimum = rawMinimum - padding;
  const maximum = rawMaximum + padding;
  const range = maximum - minimum;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const getX = (index: number, count: number) =>
    PADDING.left +
    (count <= 1 ? plotWidth / 2 : (index / (count - 1)) * plotWidth);

  const getY = (value: number) =>
    PADDING.top +
    ((maximum - value) / range) * plotHeight;

  const activeDetails =
    activeIndex === null
      ? []
      : visibleSeries
          .map((item) => ({
            series: item,
            point: item.points[activeIndex],
          }))
          .filter(
            (entry): entry is {
              series: ChartSeries;
              point: ChartPoint;
            } => Boolean(entry.point),
          );

  const tooltipPosition =
    activeIndex === null
      ? 75
      : clamp(
          (getX(activeIndex, pointCount) / WIDTH) * 100,
          12,
          88,
        );

  function toggleSeries(label: string) {
    setHiddenSeries((current) =>
      current.includes(label)
        ? current.filter((item) => item !== label)
        : [...current, label],
    );

    setActiveIndex(null);
  }

  function moveToPoint(index: number) {
    setActiveIndex(
      clamp(index, 0, Math.max(pointCount - 1, 0)),
    );
  }

  return (
    <div className="chart-wrap">
      <div className="chart-toolbar">
        <div
          className="chart-legend"
          aria-label="Chart series"
        >
          {series.map((item) => {
            const isHidden = hiddenSeries.includes(item.label);

            return (
              <button
                className={`legend-toggle ${
                  isHidden ? "is-hidden" : ""
                }`}
                key={item.label}
                type="button"
                aria-pressed={!isHidden}
                onClick={() => toggleSeries(item.label)}
              >
                <i
                  style={{ backgroundColor: item.color }}
                  aria-hidden="true"
                />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {activeDetails.length > 0 && (
          <div
            className="chart-tooltip"
            role="status"
            style={{
              left: `${tooltipPosition}%`,
              right: "auto",
            }}
          >
            <div className="tooltip-time">
              {formatTimestamp(
                activeDetails[0].point.timestamp,
                activeDetails[0].point.label,
              )}
            </div>

            <div className="tooltip-values">
              {activeDetails.map(({ series: item, point }) => (
                <div className="tooltip-series" key={item.label}>
                  <span>
                    <i
                      style={{ backgroundColor: item.color }}
                      aria-hidden="true"
                    />
                    {item.label}
                  </span>
                  <b>{formatValue(point.value)}</b>
                </div>
              ))}
            </div>

            {activeDetails[0].point.details?.length ? (
              <div className="tooltip-details">
                {activeDetails[0].point.details.map((detail) => (
                  <div
                    className="tooltip-detail"
                    key={detail.label}
                  >
                    <span>{detail.label}</span>
                    <b>{detail.value}</b>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>

      <svg
        className="line-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={chartLabel}
        onMouseLeave={() => setActiveIndex(null)}
      >
        {[0, 1, 2, 3].map((step) => {
          const value =
            maximum - (range * step) / 3;

          const y = getY(value);

          return (
            <g key={step}>
              <line
                x1={PADDING.left}
                x2={WIDTH - PADDING.right}
                y1={y}
                y2={y}
                className="chart-grid"
              />

              <text
                x={PADDING.left - 10}
                y={y + 4}
                textAnchor="end"
                className="chart-axis"
              >
                {formatValue(value)}
              </text>
            </g>
          );
        })}

        {activeIndex !== null && (
          <line
            x1={getX(activeIndex, pointCount)}
            x2={getX(activeIndex, pointCount)}
            y1={PADDING.top}
            y2={HEIGHT - PADDING.bottom}
            className="chart-crosshair"
          />
        )}

        {visibleSeries.map((item) => {
          const path = item.points
            .map(
              (point, index) =>
                `${index === 0 ? "M" : "L"} ${getX(
                  index,
                  item.points.length,
                )} ${getY(point.value)}`,
            )
            .join(" ");

          return (
            <g key={item.label}>
              {item.points.length > 1 && (
                <path
                  d={path}
                  fill="none"
                  stroke={item.color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  className="chart-line"
                />
              )}

              {item.points.map((point, index) => {
                const isActive = activeIndex === index;

                return (
                  <circle
                    key={`${item.label}-${point.timestamp ?? point.label}`}
                    className={`chart-point ${
                      isActive ? "is-active" : ""
                    }`}
                    cx={getX(index, item.points.length)}
                    cy={getY(point.value)}
                    r={isActive ? 5 : 3}
                    fill={item.color}
                    tabIndex={0}
                    role="button"
                    aria-label={`${item.label}, ${formatTimestamp(
                      point.timestamp,
                      point.label,
                    )}, ${formatValue(point.value)}`}
                    onMouseEnter={() => moveToPoint(index)}
                    onFocus={() => moveToPoint(index)}
                    onBlur={() => setActiveIndex(null)}
                    onKeyDown={(event) => {
                      if (event.key === "ArrowRight") {
                        event.preventDefault();
                        moveToPoint(index + 1);
                      }

                      if (event.key === "ArrowLeft") {
                        event.preventDefault();
                        moveToPoint(index - 1);
                      }

                      if (event.key === "Home") {
                        event.preventDefault();
                        moveToPoint(0);
                      }

                      if (event.key === "End") {
                        event.preventDefault();
                        moveToPoint(pointCount - 1);
                      }
                    }}
                  />
                );
              })}
            </g>
          );
        })}

        <text
          x={getX(0, pointCount)}
          y={HEIGHT - 10}
          textAnchor="start"
          className="chart-axis chart-axis-time"
        >
          {visibleSeries[0].points[0]?.label}
        </text>

        {pointCount > 1 && (
          <text
            x={getX(pointCount - 1, pointCount)}
            y={HEIGHT - 10}
            textAnchor="end"
            className="chart-axis chart-axis-time"
          >
            {
              visibleSeries[0].points[
                pointCount - 1
              ]?.label
            }
          </text>
        )}
      </svg>
    </div>
  );
}
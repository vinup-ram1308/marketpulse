import { SIGNAL_TYPES, SEVERITIES, type AlertSummary } from "../types";
import { Panel } from "./Panel";

const SEVERITY_COLORS = {
  LOW: "severity-low",
  MEDIUM: "severity-medium",
  HIGH: "severity-high",
} as const;

export function AlertOverview({ summary }: { summary: AlertSummary }) {
  const highTotal = summary.counts
    .filter((item) => item.severity === "HIGH")
    .reduce((total, item) => total + item.alert_count, 0);

  return (
    <Panel
      title="Alert overview"
      eyebrow="All recorded alerts"
      action={<span className="overview-total">{summary.total_alerts} total</span>}
    >
      <div className="overview-table" role="table" aria-label="Alert counts">
        <div className="overview-row overview-header" role="row">
          <span role="columnheader">Signal</span>
          {SEVERITIES.map((severity) => (
            <span className="count-cell" role="columnheader" key={severity}>
              {severity}
            </span>
          ))}
        </div>
        {SIGNAL_TYPES.map((signal) => (
          <div className="overview-row" role="row" key={signal}>
            <span className="signal-name">{signal.replaceAll("_", " ")}</span>
            {SEVERITIES.map((severity) => {
              const count =
                summary.counts.find(
                  (item) =>
                    item.signal_type === signal && item.severity === severity,
                )?.alert_count ?? 0;
              return (
                <span className="count-cell" role="cell" key={severity}>
                  {count > 0 ? (
                    <b className={`count-pill ${SEVERITY_COLORS[severity]}`}>
                      {count}
                    </b>
                  ) : (
                    <span className="zero-count">—</span>
                  )}
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <div className="severity-summary">
        {SEVERITIES.map((severity) => {
          const count = summary.counts
            .filter((item) => item.severity === severity)
            .reduce((total, item) => total + item.alert_count, 0);
          return (
            <span key={severity}>
              <i className={`severity-dot ${SEVERITY_COLORS[severity]}`} />
              {severity}
              <strong>{count}</strong>
            </span>
          );
        })}
        <span className="high-total-note">{highTotal} high severity</span>
      </div>
    </Panel>
  );
}

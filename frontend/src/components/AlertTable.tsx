import { formatDateTime } from "../format";
import type { Alert } from "../types";
import { Panel } from "./Panel";

export function AlertTable({
  alerts,
  onSelectAlert,
}: {
  alerts: Alert[];
  onSelectAlert: (alert: Alert) => void;
}) {
  return (
    <Panel
      title="Recent alerts"
      eyebrow="Actionable market signals"
      action={<span className="panel-note">{alerts.length} in current result</span>}
      className="table-panel"
    >
      {alerts.length === 0 ? (
        <div className="empty-state">
          No alerts match these filters. The market may be quiet, or the selected
          time range may have no signals.
        </div>
      ) : (
        <div className="alert-list-scroll">
          <div className="alert-list">
            {alerts.map((alert, index) => (
              <button
                className="alert-entry"
                key={`${alert.product_id}-${alert.observed_at}-${alert.signal_type}-${index}`}
                type="button"
                onClick={() => onSelectAlert(alert)}
                aria-label={`Open ${alert.severity} ${alert.signal_type.replaceAll("_", " ")} alert for ${alert.product_name}`}
              >
                <span className={`severity-badge ${alert.severity.toLowerCase()}`}>
                  <i />
                  {alert.severity}
                </span>
                <span className="alert-entry-signal">
                  {alert.signal_type.replaceAll("_", " ")}
                </span>
                <span className="alert-entry-main">
                  <strong>{alert.product_name}</strong>
                  <small>{alert.market} · {alert.product_id}</small>
                </span>
                <span className="alert-entry-message">{alert.message}</span>
                <time dateTime={alert.observed_at}>{formatDateTime(alert.observed_at)}</time>
                <span className="alert-entry-action" aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

interface KpiCardProps {
  label: string;
  value: string;
  detail: string;
  tone?: "accent" | "danger" | "positive" | "warning";
  emphasis?: boolean;
  loading?: boolean;
}

export function KpiCard({
  label,
  value,
  detail,
  tone = "accent",
  emphasis = false,
  loading = false,
}: KpiCardProps) {
  return (
    <article className={`kpi-card tone-${tone} ${emphasis ? "is-emphasis" : ""}`}>
      <p className="kpi-label">{label}</p>
      {loading ? (
        <span className="kpi-skeleton" aria-label={`${label} loading`} />
      ) : (
        <p className="kpi-value">{value}</p>
      )}
      <p className="kpi-detail">{detail}</p>
    </article>
  );
}

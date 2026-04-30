interface Props {
  label: string;
  value: string;
  sub?: string;
  accent?: "green" | "red" | "orange" | "blue";
}

export default function KpiCard({ label, value, sub, accent = "blue" }: Props) {
  return (
    <div className={`kpi-card kpi-${accent}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

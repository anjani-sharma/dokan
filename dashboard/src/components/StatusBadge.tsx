interface Props { status: string }

const colours: Record<string, string> = {
  paid: "badge-green",
  partial: "badge-orange",
  unpaid: "badge-red",
  inflow: "badge-green",
  outflow: "badge-red",
  purchase: "badge-blue",
  sale: "badge-green",
  adjustment: "badge-orange",
};

export default function StatusBadge({ status }: Props) {
  return (
    <span className={`badge ${colours[status] ?? "badge-grey"}`}>
      {status}
    </span>
  );
}

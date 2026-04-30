import { useEffect, useState } from "react";
import StatusBadge from "../components/StatusBadge";
import { fetchInvoices, fmt, Invoice } from "../api/client";

const STATUS_FILTERS = ["all", "unpaid", "partial", "paid"];

export default function Invoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchInvoices(filter === "all" ? undefined : filter)
      .then(setInvoices)
      .finally(() => setLoading(false));
  }, [filter]);

  const toggle = (id: number) => setExpanded(prev => prev === id ? null : id);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Purchase Invoices</h1>
        <div className="filter-group">
          {STATUS_FILTERS.map(s => (
            <button
              key={s}
              className={`filter-btn ${filter === s ? "active" : ""}`}
              onClick={() => setFilter(s)}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="page-loading">Loading invoices…</div>
      ) : invoices.length === 0 ? (
        <div className="empty-state">No invoices found.</div>
      ) : (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Date</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Outstanding</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invoices.map(inv => (
                <>
                  <tr key={inv.id} className="clickable-row" onClick={() => toggle(inv.id)}>
                    <td><strong>#{inv.invoice_number}</strong></td>
                    <td>{inv.invoice_date}</td>
                    <td>{fmt(inv.total_amount)}</td>
                    <td className="text-green">{fmt(inv.paid_amount)}</td>
                    <td className={inv.total_amount - inv.paid_amount > 0 ? "text-red" : ""}>
                      {fmt(inv.total_amount - inv.paid_amount)}
                    </td>
                    <td><StatusBadge status={inv.status} /></td>
                    <td className="expand-icon">{expanded === inv.id ? "▲" : "▼"}</td>
                  </tr>
                  {expanded === inv.id && (
                    <tr key={`${inv.id}-detail`} className="detail-row">
                      <td colSpan={7}>
                        <div className="detail-panel">
                          {inv.notes && <p className="detail-notes">Notes: {inv.notes}</p>}
                          {inv.items.length === 0 ? (
                            <p className="text-muted">No line items recorded.</p>
                          ) : (
                            <table className="data-table inner-table">
                              <thead>
                                <tr>
                                  <th>Product</th>
                                  <th>Qty</th>
                                  <th>Unit Cost</th>
                                  <th>Line Total</th>
                                </tr>
                              </thead>
                              <tbody>
                                {inv.items.map(item => (
                                  <tr key={item.id}>
                                    <td>{item.product_name_raw ?? `Product #${item.id}`}</td>
                                    <td>{item.qty}</td>
                                    <td>{fmt(item.unit_cost)}</td>
                                    <td>{fmt(item.qty * item.unit_cost)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

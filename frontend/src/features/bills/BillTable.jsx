import { formatCurrency } from "../../shared/format.js";
import { StatusBadge } from "../../shared/Badges.jsx";

export function BillTable({ user, allSelected, toggleAllBills, pageRows, selectedSet, toggleBillSelection, openInvoice, setModal, deleteBill }) {
  return (<div className="card table-scroll" tabIndex={0} role="region" aria-label="Scrollable records" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr style={{ borderBottom: "1px solid #21262d" }}>
              <th style={{ padding: "11px 14px", width: 42 }}>
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAllBills}
                  aria-label="Select all bills"
                />
              </th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>INVOICE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>ALLOTTEE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PERIOD</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>TOTAL</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PAID</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PENALTY</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PENALTY PAID</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>BALANCE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>STATUS</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map(b => (
              <tr key={b.id} className="row-hover" style={{ borderBottom: "1px solid #21262d" }}>
                <td style={{ padding: "10px 14px" }}>
                  <input
                    type="checkbox"
                    checked={selectedSet.has(b.id)}
                    onChange={() => toggleBillSelection(b.id)}
                    aria-label={`Select bill ${b.invoice_no || b.id}`}
                  />
                </td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#f0a500" }}>{b.invoice_no || "[Pending]"}</td>
                <td style={{ padding: "10px 14px" }}>{(b.tenant_display_name || b.tenant_name)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13 }}>{b.month_name} {b.year}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13 }}>{formatCurrency(b.total_amount)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#22c55e" }}>{formatCurrency(b.amount_paid)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#f59e0b" }}>{formatCurrency(b.penalty)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#22c55e" }}>{formatCurrency(b.penalty_paid)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: b.balance_due > 0 ? "#f59e0b" : "#8b949e" }}>{formatCurrency(b.balance_due)}</td>
                <td style={{ padding: "10px 14px" }}><StatusBadge status={b.status} /><div style={{ marginTop: 6, fontSize: 12, color: "#8b949e" }}>{b.receipt_status || (b.issue_date ? "Receipt Confirmed" : "Pending Receipt")}</div></td>
                <td style={{ padding: "10px 14px", display: "flex", gap: 6, flexWrap: "wrap" }}>

                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => openInvoice(b.id)}>Invoice</button>
                  {user?.is_superuser && b.billing_policy==='legacy_receipt' && b.billing_category!=='other' &&
                    <a className="btn-ghost" href={`/admin/estate_app/bill/${b.id}/legacy-review/`}>Review historical bill</a>}
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => setModal({ type: "editBill", data: b })}>Edit</button>
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => setModal({ type: "updateDispatch", data: b })}>{b.billing_policy === 'notices_368_369' ? 'Record email dispatch' : 'Confirm Receipt / Update Dispatch'}</button>


                  {b.status !== "Paid" && !b.is_draft && (
                    <button className="btn-primary" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => setModal({ type: "recordPayment", data: b })}>Pay</button>
                  )}
                  <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => deleteBill(b)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>);
}

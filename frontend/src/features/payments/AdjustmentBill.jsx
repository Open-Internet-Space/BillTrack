import Pagination, { usePagination } from "../../Pagination";
import { formatCurrency, formatDate } from "../../shared/format.js";

export function AdjustmentBill({ bill, splits, allSplits, resetKey }) {
  const pagination = usePagination(splits, resetKey);
  return <div className="card" style={{ padding: 0, marginBottom: 14, overflowX: "auto" }}>
    <div style={{ padding: 16, borderBottom: "1px solid #21262d" }}>
      <strong style={{ color: "#f0a500" }}>{splits[0].bill_invoice || bill?.invoice_no || "—"}</strong>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px 24px", marginTop: 8, color: "#8b949e", fontSize: 12 }}>
        <span>Bill issue date: {formatDate(bill?.issue_date)}</span>
        <span>Due date: {formatDate(bill?.due_date)}</span>
        <span>Dispatch ref: {bill?.dispatch_ref_no || "—"}</span>
        <span>Bill amount: {bill ? formatCurrency(bill.total_amount) : "—"}</span>
        <span>Adjusted principal: {bill ? formatCurrency(bill.amount_paid) : "—"}</span>
        <span>Penalty paid: {bill ? formatCurrency(bill.penalty_paid) : "—"}</span>
        <span>Principal remaining: {bill ? formatCurrency(bill.balance_due) : "—"}</span>
      </div>
    </div>
    <div style={{ padding: "0 16px" }}><Pagination pagination={pagination} label="payments" /></div>
    <table>
      <thead><tr style={{ borderBottom: "1px solid #21262d" }}>
        {['SPLIT', 'PAYMENT DATE', 'RECEIPT / PAYMENT REF', 'PRINCIPAL AMOUNT', 'PENALTY AMOUNT'].map(label =>
          <th key={label} style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e", whiteSpace: "nowrap" }}>{label}</th>
        )}
      </tr></thead>
      <tbody>{pagination.pageRows.map(p => <tr key={p.id} className="row-hover" style={{ borderBottom: "1px solid #21262d" }}>
        <td style={{ padding: "10px 14px" }}>{allSplits.indexOf(p) + 1} of {allSplits.length}</td>
        <td style={{ padding: "10px 14px" }}>{formatDate(p.payment_date)}</td>
        <td style={{ padding: "10px 14px" }}>{p.receipt_no || "—"}<small>{p.source==='security_application'?'Security application — no new cash receipt':'Receipt'}</small></td>
        <td style={{ padding: "10px 14px" }}>{formatCurrency(p.amount)}</td>
        <td style={{ padding: "10px 14px" }}>{formatCurrency(p.penalty_paid)}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

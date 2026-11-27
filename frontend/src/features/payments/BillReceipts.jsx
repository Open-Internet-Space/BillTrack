import { useEffect, useState } from "react";
import API from "../../api";
import { formatCurrency, formatDate } from "../../shared/format";

export function BillReceipts({ bill, onEditReceipt, onClose }) {
  const [state, setState] = useState({ loading: true, error: "", rows: [] });
  useEffect(() => {
    let active = true;
    API.getAll(`/payments/?bill=${bill.id}`).then(rows => {
      if (active) setState({ loading: false, error: "", rows });
    }).catch(error => {
      if (active) setState({ loading: false, error: error.message, rows: [] });
    });
    return () => { active = false; };
  }, [bill.id]);

  return <div className="estate-form">
    <h2 id="modal-title">Receipts · {bill.invoice_no || "Bill"}</h2>
    {state.loading && <p role="status">Loading receipts…</p>}
    {state.error && <p role="alert">{state.error}</p>}
    {!state.loading && !state.error && (state.rows.length ? <ul className="estate-history">
      {state.rows.map(receipt => <li key={receipt.id}>
        <span>{receipt.receipt_no || "No reference"} · {formatDate(receipt.payment_date)} · Principal {formatCurrency(receipt.amount)}
          {Number(receipt.penalty_paid) > 0 && ` · Penalty ${formatCurrency(receipt.penalty_paid)}`}</span>
        {receipt.source === "security_application" ? <small>Security application</small>
          : <button className="btn-ghost" onClick={() => onEditReceipt(receipt)}>Edit receipt</button>}
      </li>)}
    </ul> : <p>No receipts recorded for this bill.</p>)}
    <button className="btn-ghost" onClick={onClose}>Close</button>
  </div>;
}

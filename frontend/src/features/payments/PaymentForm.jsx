import { useState } from "react";
import { formatCurrency } from "../../shared/format.js";

export function PaymentForm({ bill, onSave, onClose }) {
  const billPayable = Number(bill.balance_due || 0) + Number(bill.penalty || 0);
  const previousBalance = Number(bill.previous_balance || 0);
  const previousPenalty = Number(bill.previous_penalty || 0);
  const hasPreviousDues = previousBalance > 0 || previousPenalty > 0;
  const [form, setForm] = useState({
    bill: bill.id,
    amount: Number(bill.balance_due || 0),
    payment_date: new Date().toISOString().slice(0, 10),
    penalty_paid: bill.penalty,
    receipt_no: "",
    notes: ""
  });
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <div style={{ width: 420, maxWidth: "100%" }}>
      <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Record Payment</h2>
      <div style={{ background: "#0d1117", borderRadius: 8, padding: "12px 16px", marginBottom: 16, fontFamily: "'JetBrains Mono',monospace", fontSize: 12, lineHeight: 2 }}>
        <div><span style={{ color: "#8b949e" }}>Invoice:</span> <span style={{ color: "#e6edf3" }}>{bill.invoice_no || "[Pending]"}</span></div>
        <div><span style={{ color: "#8b949e" }}>Balance:</span> <span style={{ color: "#f59e0b" }}>{formatCurrency(bill.balance_due)}</span></div>
        {hasPreviousDues && (
          <div><span style={{ color: "#8b949e" }}>Previous Dues:</span> <span style={{ color: "#f87171" }}>{formatCurrency(previousBalance + previousPenalty)}</span></div>
        )}
        <div><span style={{ color: "#8b949e" }}>Penalty:</span> <span style={{ color: "#f87171" }}>{formatCurrency(bill.penalty)}</span></div>
        <div style={{ borderTop: "1px solid #21262d", paddingTop: 6 }}><span style={{ color: "#8b949e" }}>Total Payable:</span> <span style={{ color: "#f0a500", fontWeight: 700 }}>{formatCurrency(billPayable + previousBalance + previousPenalty)}</span></div>
      </div>
      <p id="payment-allocation" className="payment-guidance">Principal and penalty entered below are recorded against this invoice only. Previous dues belong to earlier invoices; record their payments against those invoices.</p>
      <div style={{ display: "grid", gap: 14 }}>
        <div><label htmlFor="paymentform-principal-amount">Principal Amount (₹)</label><input id="paymentform-principal-amount" aria-describedby="payment-allocation" className="inp" type="number" min="0" step="0.01" value={form.amount} onChange={e => set("amount", e.target.value)} /></div>
        <div><label htmlFor="paymentform-payment-date">Payment Date</label><input id="paymentform-payment-date" className="inp" type="date" value={form.payment_date} onChange={e => set("payment_date", e.target.value)} /></div>
        <div><label htmlFor="paymentform-penalty-paid">Penalty Paid (₹)</label><input id="paymentform-penalty-paid" className="inp" type="number" min="0" step="0.01" value={form.penalty_paid} onChange={e => set("penalty_paid", e.target.value)} /></div>
        <div><label htmlFor="paymentform-receipt-no">Receipt No.</label><input id="paymentform-receipt-no" className="inp" value={form.receipt_no} onChange={e => set("receipt_no", e.target.value)} /></div>
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={() => onSave(form)}>Record Payment</button>
      </div>
    </div>
  );
}

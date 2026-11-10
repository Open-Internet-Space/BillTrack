import { useState } from "react";

export function BillDispatchForm({ bill, onSave, onClose }) {
  const [form, setForm] = useState({
    dispatch_ref_no: bill.dispatch_ref_no || "",
    issue_date: bill.issue_date || "",
    due_date: bill.due_date || ""
  });
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const setIssueDate = (value) => {
    setForm(p => {
      const issue = value ? new Date(`${value}T00:00:00Z`) : null;
      let dueDate = p.due_date;
      if (issue && !Number.isNaN(issue.getTime())) {
        issue.setUTCDate(issue.getUTCDate() + 5);
        if (!Number.isNaN(issue.getTime())) dueDate = issue.toISOString().slice(0, 10);
      }
      return { ...p, issue_date: value, due_date: dueDate };
    });
  };

  return (
    <div style={{ width: 420, maxWidth: "100%" }}>
      <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Confirm Receipt / Update Dispatch</h2>
      <div style={{ display: "grid", gap: 14 }}>
        <div><label htmlFor="billdispatchform-bill">Bill</label><input id="billdispatchform-bill" className="inp" value={`${(bill.tenant_display_name || bill.tenant_name)} - ${bill.month_name} ${bill.year}`} disabled /></div>
        <div><label htmlFor="billdispatchform-dispatch-ref-no">Dispatch / Ref. No.</label><input id="billdispatchform-dispatch-ref-no" className="inp" value={form.dispatch_ref_no} onChange={e => set("dispatch_ref_no", e.target.value)} /></div>
        <div><label htmlFor="billdispatchform-date-of-signature-issue">Confirmed Receipt Date (Issue Date)</label><input id="billdispatchform-date-of-signature-issue" aria-describedby="billdispatchform-receipt-help" className="inp" type="date" max={new Date().toLocaleDateString("en-CA")} value={form.issue_date} onChange={e => setIssueDate(e.target.value)} /></div>
        <p id="billdispatchform-receipt-help" style={{ fontSize: 12, color: "#8b949e", margin: 0 }}>Confirm only after receipt through mail. Counting starts the following day; payment is due on day five. Leave blank to keep Pending Receipt.</p>
        <div><label htmlFor="billdispatchform-due-date">{form.issue_date ? "Due Date (calculated)" : "Tentative Due Date"}</label><input id="billdispatchform-due-date" className="inp" type="date" readOnly value={form.due_date} /></div>
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={form.issue_date > new Date().toLocaleDateString("en-CA")} onClick={() => onSave({ ...form, issue_date: form.issue_date || null })}>Save Receipt / Dispatch</button>
      </div>
    </div>
  );
}

import { useState } from "react";

export function BillEditForm({ bill, onSave, onClose }) {
  const [form, setForm] = useState({
    rent: bill.rent || "0", electric: bill.electric || "0", electric_reading: bill.electric_reading || "",
    water: bill.water || "0", gst_treatment: bill.gst_treatment || "cgst_sgst", due_date: bill.due_date || "",
    issue_date: bill.issue_date || "", dispatch_ref_no: bill.dispatch_ref_no || "", notes: bill.notes || ""
  });
  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
  const setIssueDate = issue_date => {
    if (!issue_date) return set("issue_date", issue_date);
    const dueDate = new Date(`${issue_date}T00:00:00Z`);
    dueDate.setUTCDate(dueDate.getUTCDate() + 5);
    if (Number.isNaN(dueDate.getTime())) return set("issue_date", issue_date);
    setForm(prev => ({ ...prev, issue_date, due_date: dueDate.toISOString().slice(0, 10) }));
  };
  const invalid = !form.due_date || form.issue_date > new Date().toLocaleDateString("en-CA") || [form.rent, form.electric, form.water].some(value => Number(value) < 0);

  return <div style={{ width: 560, maxWidth: "100%" }}>
    <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Edit Bill · {bill.invoice_no || `${bill.tenant_name} ${bill.month_name} ${bill.year}`}</h2>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
      <div><label htmlFor="billeditform-rent">Rent (₹)</label><input id="billeditform-rent" className="inp" type="number" step="0.01" min="0" value={form.rent} onChange={e => set("rent", e.target.value)} /></div>
      <div><label htmlFor="billeditform-electricity">Electricity (₹)</label><input id="billeditform-electricity" className="inp" type="number" step="0.01" min="0" value={form.electric} onChange={e => set("electric", e.target.value)} /></div>
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-electricity-reading">Electricity Reading</label><input id="billeditform-electricity-reading" className="inp" value={form.electric_reading} onChange={e => set("electric_reading", e.target.value)} /></div>
      <div><label htmlFor="billeditform-water">Water (₹)</label><input id="billeditform-water" className="inp" type="number" step="0.01" min="0" value={form.water} onChange={e => set("water", e.target.value)} /></div>
      <div><label htmlFor="billeditform-gst-type">GST Type</label><select id="billeditform-gst-type" className="inp" value={form.gst_treatment} onChange={e => set("gst_treatment", e.target.value)}><option value="cgst_sgst">CGST + SGST</option><option value="igst">IGST</option></select></div>
      <div><label htmlFor="billeditform-issue-date">Confirmed Receipt Date (Issue Date)</label><input id="billeditform-issue-date" className="inp" type="date" max={new Date().toLocaleDateString("en-CA")} value={form.issue_date} onChange={e => setIssueDate(e.target.value)} /></div>
      <div><label htmlFor="billeditform-due-date">{form.issue_date ? "Due Date (calculated)" : "Tentative Due Date"}</label><input id="billeditform-due-date" className="inp" type="date" required readOnly={!!form.issue_date} value={form.due_date} onChange={e => set("due_date", e.target.value)} /></div>
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-dispatch-reference-no">Dispatch / Reference No.</label><input id="billeditform-dispatch-reference-no" className="inp" value={form.dispatch_ref_no} onChange={e => set("dispatch_ref_no", e.target.value)} /></div>
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-notes">Notes</label><textarea id="billeditform-notes" className="inp" rows={3} value={form.notes} onChange={e => set("notes", e.target.value)} /></div>
    </div>
    <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
      <button className="btn-ghost" onClick={onClose}>Cancel</button>
      <button className="btn-primary" disabled={invalid} onClick={() => onSave({ ...form, issue_date: form.issue_date || null })}>Save Changes</button>
    </div>
  </div>;
}

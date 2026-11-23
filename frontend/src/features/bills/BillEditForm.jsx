import { useState } from "react";
import API from '../../api';
import { BillPreviewTable } from './BillForm';

export function BillEditForm({ bill, onSave, onClose }) {
  const notice = bill.billing_policy === 'notices_368_369';
  const [form, setForm] = useState({
    rent: bill.rent || "0", electric: bill.electric || "0", electric_reading: bill.electric_reading || "",
    water: bill.water || "0", gst_treatment: bill.gst_treatment || "cgst_sgst", due_date: bill.due_date || "",
    issue_date: bill.issue_date || "", dispatch_ref_no: bill.dispatch_ref_no || "", notes: bill.notes || "",
    full_month_rent: bill.full_month_rent ?? null,
    holiday_start_date: bill.holiday_start_date || '', holiday_end_date: bill.holiday_end_date || '',
    rent_override_reason: bill.rent_override_reason || '', rate_exception_reference: bill.rate_exception_reference || '', change_reason: ''
  });
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState('');
  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));
  const setIssueDate = issue_date => {
    if (!issue_date) return set("issue_date", issue_date);
    const dueDate = new Date(`${issue_date}T00:00:00Z`);
    dueDate.setUTCDate(dueDate.getUTCDate() + 5);
    if (Number.isNaN(dueDate.getTime())) return set("issue_date", issue_date);
    setForm(prev => ({ ...prev, issue_date, due_date: dueDate.toISOString().slice(0, 10) }));
  };
  const invalid = (!notice && !form.due_date) || form.issue_date > new Date().toLocaleDateString("en-CA")
    || [form.full_month_rent ?? form.rent, form.electric, form.water].some(value => Number(value) < 0)
    || Boolean(form.holiday_start_date) !== Boolean(form.holiday_end_date)
    || (form.holiday_start_date && form.holiday_end_date < form.holiday_start_date);
  const payload = { ...form, due_date: form.due_date || null, issue_date: form.issue_date || null,
    holiday_start_date: form.holiday_start_date || null, holiday_end_date: form.holiday_end_date || null };
  const signature = JSON.stringify(payload);
  const currentPreview = preview?.signature === signature ? preview.months : null;
  const previewAmounts = async () => {
    setPreviewing(true); setError(''); setPreview(null);
    try {
      const result = await API.post(`/bills/${bill.id}/preview/`, payload);
      setPreview({ signature, months: result.months });
    } catch (error) { setError(error.message); }
    finally { setPreviewing(false); }
  };
  const setHoliday = (key, value) => setForm(old => ({ ...old, [key]: value,
    full_month_rent: old.full_month_rent ?? old.rent }));

  return <div style={{ width: 560, maxWidth: "100%" }}>
    <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Edit Bill · {bill.invoice_no || `${(bill.tenant_display_name || bill.tenant_name)} ${bill.month_name} ${bill.year}`}</h2>
    <div className="bill-form-grid">
      <div><label htmlFor="billeditform-rent">Full-month rent (₹)</label><input id="billeditform-rent" className="inp" type="number" step="0.01" min="0" value={form.full_month_rent ?? form.rent} onChange={e => set("full_month_rent", e.target.value)} /></div>
      <div><label htmlFor="billeditform-electricity">Electricity (₹)</label><input id="billeditform-electricity" className="inp" type="number" step="0.01" min="0" value={form.electric} onChange={e => set("electric", e.target.value)} /></div>
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-electricity-reading">Electricity Reading</label><input id="billeditform-electricity-reading" className="inp" value={form.electric_reading} onChange={e => set("electric_reading", e.target.value)} /></div>
      <div><label htmlFor="billeditform-water">Water (₹)</label><input id="billeditform-water" className="inp" type="number" step="0.01" min="0" value={form.water} onChange={e => set("water", e.target.value)} /></div>
      <div><label htmlFor="billeditform-gst-type">GST Type</label><select id="billeditform-gst-type" className="inp" value={form.gst_treatment} onChange={e => set("gst_treatment", e.target.value)}><option value="cgst_sgst">CGST + SGST</option><option value="igst">IGST</option></select></div>
      <div><label htmlFor="billeditform-holiday-start">Holiday start date</label><input className="inp" id="billeditform-holiday-start" type="date" value={form.holiday_start_date} onChange={e => setHoliday('holiday_start_date', e.target.value)} /></div>
      <div><label htmlFor="billeditform-holiday-end">Holiday end date</label><input className="inp" id="billeditform-holiday-end" type="date" value={form.holiday_end_date} onChange={e => setHoliday('holiday_end_date', e.target.value)} /></div>
      <p style={{ gridColumn: '1/-1', fontSize: 12 }}>Both closure dates are included. Clear both to restore full-month rent. Existing receipts remain recorded; any excess payment stays visible for review.</p>
      {notice ? <><div style={{gridColumn:'1/-1'}}><p>Notice policy · rate {bill.rate_snapshot || 'not recorded'}/sq ft × area {bill.area_snapshot || 'not recorded'} · {bill.rent_revision_reference || 'Review rate evidence'}. Use Record email dispatch for raised/dispatch dates.</p></div>
        <div style={{gridColumn:'1/-1'}}><label htmlFor="billeditform-override">Reviewed rent override reason</label><textarea className="inp" id="billeditform-override" value={form.rent_override_reason} onChange={e=>set('rent_override_reason',e.target.value)} /></div>
        <div style={{gridColumn:'1/-1'}}><label htmlFor="billeditform-rate-exception">Approved rate exception reference</label><input className="inp" id="billeditform-rate-exception" value={form.rate_exception_reference} onChange={e=>set('rate_exception_reference',e.target.value)} /></div>
      </> : <>
      <div><label htmlFor="billeditform-issue-date">Confirmed Receipt Date (Issue Date)</label><input id="billeditform-issue-date" className="inp" type="date" max={new Date().toLocaleDateString("en-CA")} value={form.issue_date} onChange={e => setIssueDate(e.target.value)} /></div>
      <div><label htmlFor="billeditform-due-date">{form.issue_date ? "Due Date (calculated)" : "Tentative Due Date"}</label><input id="billeditform-due-date" className="inp" type="date" required readOnly={!!form.issue_date} value={form.due_date} onChange={e => set("due_date", e.target.value)} /></div>
      </>}
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-dispatch-reference-no">Dispatch / Reference No.</label><input id="billeditform-dispatch-reference-no" className="inp" value={form.dispatch_ref_no} onChange={e => set("dispatch_ref_no", e.target.value)} /></div>
      <div style={{ gridColumn: "1/-1" }}><label htmlFor="billeditform-notes">Notes</label><textarea id="billeditform-notes" className="inp" rows={3} value={form.notes} onChange={e => set("notes", e.target.value)} /></div>
      <div style={{gridColumn:'1/-1'}}><label htmlFor="billeditform-change-reason">Reason for this change</label><textarea className="inp" id="billeditform-change-reason" required maxLength={2000} value={form.change_reason} onChange={e=>set('change_reason',e.target.value)} /></div>
    </div>
    <button className="btn-ghost" style={{ marginTop: 16 }} disabled={invalid || previewing} onClick={previewAmounts}>{previewing ? 'Calculating…' : 'Preview monthly amounts'}</button>
    {error && <p role="alert">{error}</p>}
    {currentPreview ? <BillPreviewTable months={currentPreview} editing /> : <p role="status">Preview the current amounts before saving changes.</p>}
    <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
      <button className="btn-ghost" onClick={onClose}>Cancel</button>
      <button className="btn-primary" disabled={invalid || previewing || !currentPreview || !form.change_reason.trim()} onClick={() => onSave(payload)}>Save Changes</button>
    </div>
  </div>;
}

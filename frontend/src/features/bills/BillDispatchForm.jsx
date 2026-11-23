import { useState } from "react";
import API from '../../api';
import { formatDate } from '../../shared/format';
import { BillPreviewTable } from './BillForm';

export function BillDispatchForm(props) {
  return props.bill.billing_policy === 'notices_368_369' ? <NoticeDispatchForm {...props} /> : <LegacyDispatchForm {...props} />;
}

function LegacyDispatchForm({ bill, onSave, onClose }) {
  const [form, setForm] = useState({
    dispatch_ref_no: bill.dispatch_ref_no || "",
    issue_date: bill.issue_date || "",
    due_date: bill.due_date || "", change_reason: ''
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
        <div><label htmlFor="billdispatchform-change-reason">Reason for this change</label><textarea className="inp" id="billdispatchform-change-reason" required maxLength={2000} value={form.change_reason} onChange={e=>set('change_reason',e.target.value)} /></div>
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={form.issue_date > new Date().toLocaleDateString("en-CA") || !form.change_reason.trim()} onClick={() => onSave({ ...form, issue_date: form.issue_date || null })}>Save Receipt / Dispatch</button>
      </div>
    </div>
  );
}

function NoticeDispatchForm({ bill, onSave, onClose }) {
  const [form, setForm] = useState({ raised_date: bill.raised_date || '', dispatch_ref_no: bill.dispatch_ref_no || '',
    email_dispatched_at: bill.email_dispatched_at ? new Intl.DateTimeFormat('sv-SE', {timeZone: 'Asia/Kolkata',
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(new Date(bill.email_dispatched_at)).replace(' ', 'T') : '',
    dispatch_recipient: bill.dispatch_recipient || '', dispatch_message_reference: bill.dispatch_message_reference || '', change_reason: '' });
  const [confirmed, setConfirmed] = useState(false);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = key => event => setForm(old => ({ ...old, [key]: event.target.value }));
  const payload = { ...form, raised_date: form.raised_date || null,
    email_dispatched_at: form.email_dispatched_at ? new Date(`${form.email_dispatched_at}+05:30`).toISOString() : null };
  const signature = JSON.stringify(payload);
  const ready = preview?.signature === signature;
  const invalid = Boolean(form.email_dispatched_at && (!confirmed || !form.raised_date || !form.dispatch_recipient.trim() || !form.dispatch_message_reference.trim()));
  const calculate = async () => {
    setBusy(true); setError(''); setPreview(null);
    try { const result = await API.post(`/bills/${bill.id}/preview/`, payload); setPreview({ signature, month: result.months[0] }); }
    catch (error) { setError(error.message); }
    finally { setBusy(false); }
  };
  return <div style={{ width: 520, maxWidth: '100%' }}>
    <h2 id="modal-title">Notice dates and email dispatch</h2>
    <p className="payment-guidance">Payment is due seven calendar days after raising. Confirmed dispatch starts interest only after the later of dispatch and that deadline. Saving here sends no email.</p>
    <div className="bill-form-grid">
      <div><label htmlFor="notice-raised">Invoice raised date</label><input className="inp" id="notice-raised" type="date" value={form.raised_date} onChange={set('raised_date')} /></div>
      <div><label htmlFor="notice-office-reference">Office dispatch / reference</label><input className="inp" id="notice-office-reference" value={form.dispatch_ref_no} onChange={set('dispatch_ref_no')} /></div>
      <div style={{gridColumn:'1/-1'}}><label htmlFor="notice-dispatch-time">Confirmed email dispatch (India time)</label><input className="inp" id="notice-dispatch-time" type="datetime-local" value={form.email_dispatched_at} onChange={set('email_dispatched_at')} /></div>
      <div style={{gridColumn:'1/-1'}}><label htmlFor="notice-dispatch-recipient">Actual email recipient</label><input className="inp" id="notice-dispatch-recipient" type="email" value={form.dispatch_recipient} onChange={set('dispatch_recipient')} /></div>
      <div style={{gridColumn:'1/-1'}}><label htmlFor="notice-dispatch-reference">Confirmed message / provider reference</label><input className="inp" id="notice-dispatch-reference" value={form.dispatch_message_reference} onChange={set('dispatch_message_reference')} /></div>
      {form.email_dispatched_at && <label style={{gridColumn:'1/-1'}} htmlFor="notice-dispatch-confirmed"><input id="notice-dispatch-confirmed" type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> I verified successful email transmission and this evidence.</label>}
      <div style={{gridColumn:'1/-1'}}><label htmlFor="notice-change-reason">Reason for this change</label><textarea className="inp" id="notice-change-reason" required maxLength={2000} value={form.change_reason} onChange={set('change_reason')} /></div>
    </div>
    <button className="btn-ghost" disabled={invalid || busy} onClick={calculate}>{busy ? 'Checking…' : 'Preview deadline'}</button>
    {error && <p role="alert">{error}</p>}
    {ready && <><p aria-label="Notice deadline preview">{preview.month.receipt_status} · Due {formatDate(preview.month.due_date)}</p><BillPreviewTable months={[preview.month]} editing /></>}
    <div className="estate-form-actions"><button className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={invalid || busy || !ready || !form.change_reason.trim()} onClick={() => onSave(payload)}>Save notice dates / dispatch</button></div>
  </div>;
}

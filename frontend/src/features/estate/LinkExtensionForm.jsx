import { useEffect, useState } from 'react';
import API from '../../api';
import { formatCurrency, formatDate } from '../../shared/format';
import { Field, FormActions } from './EstateForms';

const termLabel = term => `${term.award_reference} · ${formatDate(term.start_date)} – ${formatDate(term.effective_end || term.end_date)}`;

export function LinkExtensionForm({ term, candidates, onSave, onClose }) {
  const [form, setForm] = useState({ previous_id: '', approval: term.approval_reference || '',
    performance: term.performance_reference || '', reason: '', move_fee: false });
  const [fees, setFees] = useState({ loading: true, rows: [], error: '' });
  useEffect(() => {
    let active = true;
    API.getAll(`/estate-charges/?kind=extension_fee&allotment__tenant=${term.tenant}`)
      .then(rows => { if (active) setFees({ loading: false, rows, error: '' }); })
      .catch(error => { if (active) setFees({ loading: false, rows: [], error: error.message }); });
    return () => { active = false; };
  }, [term.tenant]);
  const set = field => value => setForm(previous => ({ ...previous, [field]: value }));
  const termFee = fees.rows.find(fee => fee.allotment === term.id);
  const precedingFee = fees.rows.find(fee => fee.allotment === Number(form.previous_id));
  return <form className="estate-form" aria-label="Link existing extension" onSubmit={event => {
    event.preventDefault();
    if (!fees.loading && !fees.error && event.currentTarget.reportValidity()) onSave(form);
  }}>
    <h2 id="modal-title">Link as extension</h2>
    <p>{termLabel(term)}</p>
    <p className="payment-guidance">The term keeps its invoices and receipts. Its recorded rent rates join the original award’s schedule.</p>
    <div className="estate-form-grid">
      <label className="estate-wide" htmlFor="extension-preceding-term">Preceding term<select id="extension-preceding-term" className="inp" required value={form.previous_id}
        onChange={event => setForm(previous => ({ ...previous, previous_id: event.target.value, move_fee: false }))}>
        <option value="">Choose the preceding term</option>
        {candidates.map(candidate => <option key={candidate.id} value={candidate.id}>{termLabel(candidate)}</option>)}
      </select></label>
      <Field id="extension-approval" label="Renewal approval reference" value={form.approval} onChange={set('approval')} required maxLength={250} />
      <Field id="extension-performance" label="Satisfactory performance reference" value={form.performance} onChange={set('performance')} required maxLength={250} />
      <Field id="extension-reason" label="Reason for linking these terms" value={form.reason} onChange={set('reason')} required maxLength={2000} />
      {fees.loading && <p role="status">Checking extension fees…</p>}
      {fees.error && <p role="alert">Could not check extension fees. {fees.error}</p>}
      {precedingFee && <p className="estate-wide">The preceding term’s extension fee will be linked. Balance {formatCurrency(precedingFee.balance_due)}.</p>}
      {form.previous_id && termFee && !precedingFee && <label className="estate-checkbox estate-wide">
        <input type="checkbox" checked={form.move_fee} onChange={event => set('move_fee')(event.target.checked)} />
        Use the existing fee on this term for this extension ({termFee.description}, balance {formatCurrency(termFee.balance_due)})
      </label>}
    </div>
    <FormActions onClose={onClose} label="Link as extension" disabled={fees.loading || Boolean(fees.error)} />
  </form>;
}

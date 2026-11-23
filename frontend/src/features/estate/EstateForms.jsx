import { useState } from 'react';
import { allotteeLabel } from '../../shared/format';
import API from '../../api';

export function Field({ id, label, value, onChange, ...props }) {
  return <label htmlFor={id}>{label}<input id={id} className="inp" value={value ?? ''}
    onChange={event => onChange(event.target.value)} {...props} /></label>;
}

function initialValues(defaults, data) {
  return Object.fromEntries(Object.entries(defaults).map(([key, value]) => [key, data?.[key] ?? value]));
}

export function FormActions({ onClose, label = 'Save record' }) {
  return <div className="estate-form-actions"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
    <button type="submit" className="btn-primary">{label}</button></div>;
}

export function ShopForm({ shop, onSave, onClose }) {
  const [form, setForm] = useState(() => initialValues({ code: '', name: '', location: '', category: 'utility',
    space_type: 'space', advertised_area: '', authorized_services: '', opens_at: '', closes_at: '',
    hours_exception_reference: '', active: true, availability_confirmed_on: '', availability_reference: '', change_reason: '' }, shop));
  const set = key => value => setForm(old => ({ ...old, [key]: value }));
  return <form aria-label="Shop details" className="estate-form" onSubmit={event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    onSave({ ...form, advertised_area: form.advertised_area || null, opens_at: form.opens_at || null,
      closes_at: form.closes_at || null, availability_confirmed_on: form.availability_confirmed_on || null });
  }}>
    <h2 id="modal-title">{shop ? 'Edit shop' : 'Add shop'}</h2>
    <div className="estate-form-grid">
      <Field id="shop-code" label="Shop code" value={form.code} onChange={set('code')} required maxLength={50} />
      <Field id="shop-name" label="Shop name" value={form.name} onChange={set('name')} required maxLength={200} />
      <Field id="shop-location" label="Location" value={form.location} onChange={set('location')} maxLength={250} />
      <label htmlFor="shop-category">Category<select id="shop-category" className="inp" value={form.category} onChange={e => set('category')(e.target.value)}>
        <option value="day_food">Day food shop</option><option value="utility">Utility shop</option><option value="night_utility">Night utility shop</option></select></label>
      <label htmlFor="shop-space-type">Type<select id="shop-space-type" className="inp" value={form.space_type} onChange={e => set('space_type')(e.target.value)}><option value="space">Space</option><option value="room">Constructed room</option></select></label>
      <Field id="shop-advertised-area" label="Advertised area (sq ft, approximate)" type="number" min="0.0001" step="0.0001" value={form.advertised_area} onChange={set('advertised_area')} />
      <label className="estate-wide" htmlFor="shop-services">Authorized goods / services<textarea id="shop-services" className="inp" value={form.authorized_services} onChange={e => set('authorized_services')(e.target.value)} /></label>
      <Field id="shop-opens" label="Permitted opening time" type="time" value={form.opens_at} onChange={set('opens_at')} />
      <Field id="shop-closes" label="Permitted closing time (may be next day)" type="time" value={form.closes_at} onChange={set('closes_at')} />
      <Field id="shop-hours-reference" label="Approved hours exception reference" value={form.hours_exception_reference} onChange={set('hours_exception_reference')} />
      <label className="estate-checkbox"><input type="checkbox" checked={form.active} onChange={e => set('active')(e.target.checked)} /> Active shop</label>
    </div>
    <h3>Initial availability evidence</h3><p className="payment-guidance">Confirm the space was available before recording its first possession. Contract expiry alone does not confirm vacancy.</p>
    <div className="estate-form-grid"><Field id="shop-available-date" label="Availability confirmed on" type="date" value={form.availability_confirmed_on} onChange={set('availability_confirmed_on')} />
      <Field id="shop-availability-reference" label="Availability reference" value={form.availability_reference} onChange={set('availability_reference')} required={Boolean(form.availability_confirmed_on)} /></div>
    {shop && <Field id="shop-change-reason" label="Reason for this change" value={form.change_reason} onChange={set('change_reason')} required maxLength={2000} />}
    <FormActions onClose={onClose} label={shop ? 'Save shop' : 'Add shop'} />
  </form>;
}

function renewalDates(term) {
  if (!term) return {};
  const start = new Date(`${term.effective_end || term.end_date}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() + 1);
  const end = new Date(start);
  end.setUTCFullYear(end.getUTCFullYear() + 1);
  end.setUTCDate(end.getUTCDate() - 1);
  return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) };
}

export function AllotmentForm({ term, renewalOf, shop, shops, tenants, onSave, onClose }) {
  const availableTenants = tenants.filter(t => t.active || t.id === term?.tenant || t.id === renewalOf?.tenant);
  const [form, setForm] = useState(() => ({ ...initialValues({ shop: shop || (shops.length === 1 ? shops[0].id : ''),
    tenant: availableTenants.length === 1 ? availableTenants[0].id : '', source_notice: '368/2025', award_reference: '',
    letter_issued_on: '', start_date: '', end_date: '', actual_area: '', measurement_reference: '', approved_rate_reference: '',
    exception_reference: '', notes: '', termination_date: '', termination_reference: '', renewal_of: null,
    performance_reference: '', approval_reference: '', possession_date: '', possession_reference: '',
    handover_date: '', handover_reference: '', vacation_deadline: '', vacation_reference: '', change_reason: '' }, term || renewalOf),
    ...(renewalOf ? { ...renewalDates(renewalOf), renewal_of: renewalOf.id, award_reference: '', letter_issued_on: '',
      performance_reference: '', approval_reference: '', possession_date: '', possession_reference: '',
      handover_date: '', handover_reference: '', termination_date: '', termination_reference: '',
      vacation_deadline: '', vacation_reference: '', exception_reference: '' } : {}) }));
  const set = key => value => setForm(old => ({ ...old, [key]: value }));
  const input = (key, label, options = {}) => <Field key={key} id={`term-${key}`} label={label} value={form[key]} onChange={set(key)} {...options} />;
  return <form aria-label="Allotment form" className="estate-form" onSubmit={event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    const payload = { ...form };
    ['termination_date', 'possession_date', 'handover_date', 'vacation_deadline'].forEach(key => { payload[key] = payload[key] || null; });
    onSave(payload);
  }}>
    <h2 id="modal-title">{term ? 'Edit allotment / handover' : renewalOf ? 'Record approved renewal' : 'Record allotment'}</h2>
    {renewalOf && <p className="payment-guidance">Keep the previous term in history. Confirm the new letter, dates, performance and approval references.</p>}
    <div className="estate-form-grid">
      <label htmlFor="term-shop">Shop<select id="term-shop" className="inp" required value={form.shop} disabled={Boolean(form.renewal_of)} onChange={e => set('shop')(e.target.value)}>
        <option value="">Choose a shop</option>{shops.map(item => <option key={item.id} value={item.id} disabled={!item.active && item.id !== Number(form.shop)}>{item.code} — {item.name}{!item.active ? ' (retired)' : ''}</option>)}</select></label>
      <label htmlFor="term-tenant">Allottee<select id="term-tenant" className="inp" required value={form.tenant} disabled={Boolean(form.renewal_of)} onChange={e => set('tenant')(e.target.value)}>
        <option value="">Choose an allottee</option>{availableTenants.map(item => <option key={item.id} value={item.id}>{allotteeLabel(item)}</option>)}</select></label>
      {input('source_notice', 'Source notice', { required: true })}{input('award_reference', 'Award / extension letter reference', { required: true })}
      {input('letter_issued_on', 'Letter issued on', { type: 'date', required: true })}{input('start_date', 'Term start date', { type: 'date', required: true })}
      {input('end_date', 'Term end date (inclusive)', { type: 'date', required: true, min: form.start_date || undefined })}
      {input('actual_area', 'Actual allotted area (sq ft)', { type: 'number', min: '0.0001', step: '0.0001', required: true })}
      {input('measurement_reference', 'Measurement reference', { required: true })}{input('approved_rate_reference', 'Accepted rate reference')}
      {input('performance_reference', 'Satisfactory performance reference', { required: Boolean(form.renewal_of) })}
      {input('approval_reference', 'Renewal approval reference', { required: Boolean(form.renewal_of) })}
      {input('exception_reference', 'Approved date / duration exception reference')}
    </div>
    <details className="estate-form-section"><summary>Possession, termination and physical handover</summary><div className="estate-form-grid">
      {input('possession_date', 'Possession date', { type: 'date' })}{input('possession_reference', 'Possession reference', { required: Boolean(form.possession_date) })}
      {input('termination_date', 'Effective termination date', { type: 'date' })}{input('termination_reference', 'Termination order reference', { required: Boolean(form.termination_date) })}
      {input('handover_date', 'Actual handover date', { type: 'date' })}{input('handover_reference', 'Handover evidence reference', { required: Boolean(form.handover_date) })}
      {input('vacation_deadline', 'Approved alternative vacation deadline', { type: 'date' })}{input('vacation_reference', 'Alternative deadline reference', { required: Boolean(form.vacation_deadline) })}
    </div></details>
    <label htmlFor="term-notes">Notes<textarea id="term-notes" className="inp" value={form.notes} onChange={e => set('notes')(e.target.value)} /></label>
    {term && input('change_reason', 'Reason for this change', { required: true, maxLength: 2000 })}
    <FormActions onClose={onClose} label={term ? 'Save allotment' : renewalOf ? 'Record renewal' : 'Record allotment'} />
  </form>;
}

export function RequirementForm({ requirement, onSave, onClose }) {
  const [form, setForm] = useState(() => initialValues({ applicable: true, not_applicable_reason: '',
    due_date: '', submitted_on: '', submission_reference: '', verified_on: '', unresolved_issue: '', change_reason: '' }, requirement));
  const set = key => value => setForm(old => ({ ...old, [key]: value }));
  return <form aria-label="Requirement evidence" className="estate-form" onSubmit={event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    onSave({ ...form, due_date: form.due_date || null, submitted_on: form.submitted_on || null, verified_on: form.verified_on || null });
  }}><h2 id="modal-title">Update {requirement.kind} evidence</h2>
    <p className="payment-guidance">Verification records your signed-in account. Enter the date and reference of the document you checked.</p>
    <label className="estate-checkbox"><input type="checkbox" checked={form.applicable} onChange={e => set('applicable')(e.target.checked)} /> Applicable to this allotment</label>
    <div className="estate-form-grid">
      <Field id="requirement-not-applicable" label="Reason if not applicable" value={form.not_applicable_reason} onChange={set('not_applicable_reason')} required={!form.applicable} />
      <Field id="requirement-due" label="Due date" type="date" value={form.due_date} onChange={set('due_date')} />
      <Field id="requirement-submitted" label="Submitted on" type="date" value={form.submitted_on} onChange={set('submitted_on')} />
      <Field id="requirement-reference" label="Submission reference" value={form.submission_reference} onChange={set('submission_reference')} required={Boolean(form.submitted_on)} />
      <Field id="requirement-verified" label="Verified on" type="date" value={form.verified_on} onChange={set('verified_on')} min={form.submitted_on || undefined} />
      <Field id="requirement-issue" label="Unresolved issue" value={form.unresolved_issue} onChange={set('unresolved_issue')} />
    </div>
    <Field id="requirement-reason" label="Reason for this change" value={form.change_reason} onChange={set('change_reason')} required maxLength={2000} />
    <FormActions onClose={onClose} label="Save evidence" />
  </form>;
}

export function RentRevisionForm({ originalAward, rate, previousRate, onSave, onClose }) {
  const [form, setForm] = useState(() => initialValues({ effective_date: '', rate: '', approval_reference: '',
    reason: '', exception_reference: '', change_reason: '' }, rate));
  const [preview, setPreview] = useState({ busy:false, error:'', message:'' });
  const set = key => value => setForm(old => ({...old,[key]:value}));
  const calculate = async () => {
    const asOf = previousRate.effective_date;
    const year = Math.max(2026, Number(asOf.slice(0,4)) + (asOf.slice(5) >= '04-01' ? 1 : 0));
    setPreview({busy:true,error:'',message:''});
    try {
      const result = await API.get(`/rent-revisions/${previousRate.id}/annual-preview/?through=${form.effective_date || `${year}-04-01`}`);
      const next = result.revisions[0];
      if (next) setForm(old=>({...old, effective_date:next.effective_date, rate:next.rate}));
      setPreview({busy:false,error:'',message:next ? 'Proposed increase only. Record the actual approval before saving.' : 'No unapproved annual increase through that date.'});
    } catch(error) {setPreview({busy:false,error:error.message,message:''});}
  };
  return <form className="estate-form" aria-label="Reviewed rent rate" onSubmit={event=>{
    event.preventDefault(); if(!event.currentTarget.reportValidity()) return;
    onSave({...form,original_award:originalAward});
  }}><h2 id="modal-title">{rate ? 'Correct rate evidence' : previousRate ? 'Record approved rent revision' : 'Record accepted rate'}</h2>
    <p className="payment-guidance">Record the actual accepted rate and its as-of date. Renewals share this original award's schedule. Previous increases already included in that rate will not be repeated.</p>
    <div className="estate-form-grid">
      <Field id="rate-effective" label="Effective / accepted rate as-of date" type="date" required value={form.effective_date} onChange={set('effective_date')} />
      <Field id="rate-amount" label="Rate per sq ft per month (₹)" type="number" min="0.0001" step="0.0001" required value={form.rate} onChange={set('rate')} />
      <Field id="rate-approval" label="Accepted bid / revision approval reference" required value={form.approval_reference} onChange={set('approval_reference')} maxLength={250} />
      <Field id="rate-reason" label="Reason / reviewed basis" required value={form.reason} onChange={set('reason')} />
      <Field id="rate-exception" label="Authorized exception reference, if applicable" value={form.exception_reference} onChange={set('exception_reference')} maxLength={250} />
      {rate && <Field id="rate-change-reason" label="Reason for this change" required value={form.change_reason} onChange={set('change_reason')} maxLength={2000} />}
    </div>
    {previousRate && !rate && <button type="button" className="btn-ghost" disabled={preview.busy} onClick={calculate}>{preview.busy ? 'Calculating…' : 'Preview 5% April increase'}</button>}
    {preview.error && <p role="alert">{preview.error}</p>}{preview.message && <p role="status">{preview.message}</p>}
    <FormActions onClose={onClose} label={rate ? 'Save rate evidence' : 'Record approved rate'} />
  </form>;
}

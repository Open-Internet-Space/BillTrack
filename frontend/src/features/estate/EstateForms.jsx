import { useEffect, useState } from 'react';
import { allotteeLabel, formatCurrency } from '../../shared/format';
import API from '../../api';
import { calculateFullMonthRent } from '../bills/RentEntryFields';
import { ModalOverlay } from '../../shared/ModalOverlay';

export function Field({ id, label, value, onChange, ...props }) {
  return <label htmlFor={id}>{label}<input id={id} className="inp" value={value ?? ''}
    onChange={event => onChange(event.target.value)} {...props} /></label>;
}

function initialValues(defaults, data) {
  return Object.fromEntries(Object.entries(defaults).map(([key, value]) => [key, data?.[key] ?? value]));
}

export function FormActions({ onClose, label = 'Save record', disabled }) {
  return <div className="estate-form-actions"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
    <button type="submit" className="btn-primary" disabled={disabled}>{label}</button></div>;
}

export function ShopForm({ shop, onSave, onClose }) {

  const [form, setForm] = useState(() => initialValues({ code: '', name: '', location: '', category: 'utility',

    space_type: 'space', advertised_area: '', authorized_services: '', opens_at: '', closes_at: '',

    hours_exception_reference: '', active: true, availability_confirmed_on: '', availability_reference: '', change_reason: '' }, shop));

  const set = key => value => setForm(old => ({ ...old, [key]: value }));

  return <form aria-label="Premises details" className="estate-form" onSubmit={event => {

    event.preventDefault();

    if (!event.currentTarget.reportValidity()) return;

    onSave({ ...form, advertised_area: form.advertised_area || null, opens_at: form.opens_at || null,

      closes_at: form.closes_at || null, availability_confirmed_on: form.availability_confirmed_on || null });

  }}>

    <h2 id="modal-title">{shop ? 'Edit premises' : 'Add premises'}</h2>

    <div className="estate-form-grid">

      <Field id="shop-code" label="Premises code" value={form.code} onChange={set('code')} required maxLength={50} />

      <Field id="shop-name" label="Premises name" value={form.name} onChange={set('name')} required maxLength={200} />

      <Field id="shop-location" label="Location" value={form.location} onChange={set('location')} maxLength={250} />

      <label htmlFor="shop-category">Category<select id="shop-category" className="inp" value={form.category} onChange={e => set('category')(e.target.value)}>

        <option value="day_food">Daytime food service</option><option value="utility">Utility or other service</option><option value="night_utility">Night-time utility service</option></select></label>

      <label htmlFor="shop-space-type">Type<select id="shop-space-type" className="inp" value={form.space_type} onChange={e => set('space_type')(e.target.value)}><option value="space">Space</option><option value="room">Constructed room</option></select></label>

      <Field id="shop-advertised-area" label="Advertised area (sq ft, approximate)" type="number" min="0.0001" step="0.0001" value={form.advertised_area} onChange={set('advertised_area')} />

      <label className="estate-wide" htmlFor="shop-services">Authorized goods / services<textarea id="shop-services" className="inp" value={form.authorized_services} onChange={e => set('authorized_services')(e.target.value)} /></label>

      <Field id="shop-opens" label="Permitted opening time" type="time" value={form.opens_at} onChange={set('opens_at')} />

      <Field id="shop-closes" label="Permitted closing time (may be next day)" type="time" value={form.closes_at} onChange={set('closes_at')} />

      <Field id="shop-hours-reference" label="Approved hours exception reference" value={form.hours_exception_reference} onChange={set('hours_exception_reference')} />

      <label className="estate-checkbox"><input type="checkbox" checked={form.active} onChange={e => set('active')(e.target.checked)} /> Active</label>

    </div>

    <h3>Initial availability evidence</h3><p className="payment-guidance">Confirm the space was available before recording its first possession. Contract expiry alone does not confirm vacancy.</p>

    <div className="estate-form-grid"><Field id="shop-available-date" label="Availability confirmed on" type="date" value={form.availability_confirmed_on} onChange={set('availability_confirmed_on')} />

      <Field id="shop-availability-reference" label="Availability reference" value={form.availability_reference} onChange={set('availability_reference')} required={Boolean(form.availability_confirmed_on)} /></div>

    {shop && <Field id="shop-change-reason" label="Reason for this change" value={form.change_reason} onChange={set('change_reason')} required maxLength={2000} />}

    <FormActions onClose={onClose} label={shop ? 'Save premises' : 'Add premises'} />

  </form>;

}



function yearlyEnd(date) {
  const end = new Date(`${date}T00:00:00Z`);
  end.setUTCFullYear(end.getUTCFullYear() + 1);
  end.setUTCDate(end.getUTCDate() - 1);
  return end.toISOString().slice(0, 10);
}

function renewalDates(term) {
  if (!term) return {};
  const start = new Date(`${term.effective_end || term.end_date}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() + 1);
  const start_date = start.toISOString().slice(0, 10);
  return { start_date, end_date: yearlyEnd(start_date) };
}

function dateExceptions({ letter_issued_on, start_date, end_date, renewal_of }) {
  if (!letter_issued_on || !start_date || !end_date) return [];
  const messages = [];
  if (start_date < letter_issued_on) messages.push('The term starts before the allotment letter was issued.');
  if (end_date > yearlyEnd(renewal_of ? start_date : letter_issued_on)) {
    messages.push(renewal_of ? 'The renewal exceeds one year from its start date.' : 'The term extends beyond one year from the letter date.');
  }
  return messages;
}

const exceptionDates = term => [term.letter_issued_on, term.start_date, term.end_date].join('|');

function DateExceptionDialog({ messages, reference, reason, onClose, onConfirm }) {
  const [approval, setApproval] = useState(reference);
  const [explanation, setExplanation] = useState(reason);
  return <ModalOverlay titleId="date-exception-title" onClose={onClose}>
    <form className="estate-form" aria-label="Allotment date exception" onSubmit={event => {
      event.preventDefault();
      if (!approval.trim() || !explanation.trim()) return;
      onConfirm({ exception_reference: approval.trim(), exception_reason: explanation.trim() });
    }}>
      <h2 id="date-exception-title">Record date exception</h2>
      <ul>{messages.map(message => <li key={message}>{message}</li>)}</ul>
      <Field id="date-exception-approval" label="Approved exception reference" value={approval} onChange={setApproval} required maxLength={250} />
      <label htmlFor="date-exception-reason">Reason for the exception<textarea id="date-exception-reason" className="inp" rows={3} required maxLength={2000}
        value={explanation} onChange={event => setExplanation(event.target.value)} /></label>
      <FormActions onClose={onClose} label="Save with exception" disabled={!approval.trim() || !explanation.trim()} />
    </form>
  </ModalOverlay>;
}

const essentialFields = ['award_reference', 'letter_issued_on', 'start_date', 'end_date', 'rent_basis',
  'accepted_rate_amount', 'approved_rate_reference'];
const areaFields = ['actual_area', 'measurement_reference'];
const additionalFields = [
  'source_notice', 'measurement_reference', 'approved_rate_reference', 'exception_reference', 'exception_reason',
  'possession_date', 'possession_reference', 'termination_date', 'termination_reference',
  'handover_date', 'handover_reference', 'vacation_deadline', 'vacation_reference',
];

export function AllotmentForm({ term, draft, renewalOf, tenant, tenants = [], premisesEnabled, additionalDetails, onSave, onClose, onEdit, register, contractEnabled = true }) {
  const availableTenants = tenants.filter(t => t.active || t.id === term?.tenant || t.id === renewalOf?.tenant);
  const [form, setForm] = useState(() => ({ ...initialValues({ tenant: tenant ?? (availableTenants.length === 1 ? availableTenants[0].id : ''), source_notice: '', award_reference: '',
    letter_issued_on: '', start_date: '', end_date: '', rent_basis: 'area', actual_area: '', measurement_reference: '', approved_rate_reference: '',
    exception_reference: '', exception_reason: '', notes: '', termination_date: '', termination_reference: '', renewal_of: null,
    performance_reference: '', approval_reference: '', carry_forward_deposit: false, possession_date: '', possession_reference: '',
    handover_date: '', handover_reference: '', vacation_deadline: '', vacation_reference: '', change_reason: '' }, term || renewalOf || draft?.fields),
    ...(renewalOf ? { ...renewalDates(renewalOf), renewal_of: renewalOf.id, award_reference: '', letter_issued_on: '',
      performance_reference: '', approval_reference: '', carry_forward_deposit: false, possession_date: '', possession_reference: '',
      handover_date: '', handover_reference: '', termination_date: '', termination_reference: '',
      vacation_deadline: '', vacation_reference: '', exception_reference: '', exception_reason: '' } : {}) }));
  const [pendingException, setPendingException] = useState(null);
  const [confirmedDates, setConfirmedDates] = useState(null);
  const [contractDirty, setContractDirty] = useState(false);
  const [amount, setAmount] = useState(draft?.fields?.accepted_rate_amount ?? '');
  const [asOf, setAsOf] = useState(draft?.fields?.accepted_rate_as_of ?? '');
  const [unavailable, setUnavailable] = useState(draft?.unavailable ?? []);
  const canDraft = Boolean(register && !term);
  const savedRate = (term || renewalOf)?.accepted_rate;
  const flat = form.rent_basis === 'flat' && !unavailable.includes('rent_basis');
  const showArea = !flat && !unavailable.includes('rent_basis');
  const shownEssential = [...essentialFields, ...(showArea ? areaFields : [])]
    .filter(key => additionalDetails || !additionalFields.includes(key));
  const missing = unavailable.filter(key => shownEssential.includes(key));
  const calculated = showArea && !missing.some(key => key === 'actual_area' || key === 'accepted_rate_amount') && calculateFullMonthRent(form.actual_area, amount || savedRate?.amount || '');
  const [shop, setShop] = useState(term?.shop ?? renewalOf?.shop ?? '');
  const [premises, setPremises] = useState({ rows: [], error: '', loading: premisesEnabled });
  useEffect(() => {
    if (!premisesEnabled || !contractEnabled) return;
    let active = true;
    API.getAll('/shops/').then(rows => {
      if (active) setPremises({ rows, error: '', loading: false });
    }).catch(error => {
      if (active) setPremises({ rows: [], error: error.message, loading: false });
    });
    return () => { active = false; };
  }, [premisesEnabled, contractEnabled]);
  const set = key => value => setForm(old => ({ ...old, [key]: value }));
  const availabilityBox = (key, label) => canDraft && <label className="estate-checkbox">
    <input type="checkbox" aria-label={`${label} Not Available`} checked={unavailable.includes(key)}
      onChange={event => {
        const checked = event.target.checked;
        setUnavailable(previous => checked ? [...previous, key] : previous.filter(field => field !== key));
      }} /> Not Available
  </label>;
  const input = (key, label, options = {}) => {
    const field = <Field id={`term-${key}`} label={label} value={form[key]} onChange={set(key)} {...options}
      disabled={unavailable.includes(key)} />;
    return canDraft && (essentialFields.includes(key) || areaFields.includes(key))
      ? <div key={key}>{field}{availabilityBox(key, label)}</div> : field;
  };
  const amountLabel = unavailable.includes('rent_basis') ? 'Agreed charge amount'
    : flat ? 'Flat monthly charge (₹)' : 'Accepted monthly rate (₹ per sq ft)';
  const submit = payload => onSave(register && term ? { ...payload, id: term.id } : payload);
  return <><form aria-label={register ? "Allotment register form" : "Allotment form"} className="estate-form"
    onChangeCapture={onEdit}
    onInvalidCapture={event => { const details = event.target.closest('details'); if (details) details.open = true; }}
    onSubmit={event => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    if (!contractEnabled || (register && term && !contractDirty)) {
      onSave();
      return;
    }
    const payload = { ...form, actual_area: flat ? null : form.actual_area };
    if (flat) payload.measurement_reference = '';
    if (canDraft && missing.length) payload.unavailable = missing;
    if (unavailable.includes('rent_basis')) {
      delete payload.actual_area;
      delete payload.measurement_reference;
    }
    if (!savedRate && !form.renewal_of && amount) {
      payload.accepted_rate_amount = amount;
      if (asOf && (additionalDetails || draft?.fields?.accepted_rate_as_of)) payload.accepted_rate_as_of = asOf;
    }
    if (premisesEnabled && !renewalOf && !premises.loading && !premises.error) {
      payload.shop = shop || null;
    }
    ['termination_date', 'possession_date', 'handover_date', 'vacation_deadline'].forEach(key => { payload[key] = payload[key] || null; });
    if (!additionalDetails) {
      for (const key of additionalFields) {
        if (!draft?.fields || !(key in draft.fields)) delete payload[key];
      }
    }
    const messages = missing.length ? [] : dateExceptions(form);
    if (messages.length) {
      const dates = exceptionDates(form);
      if (dates === confirmedDates && form.exception_reference.trim() && form.exception_reason.trim()) {
        payload.exception_reference = form.exception_reference;
        payload.exception_reason = form.exception_reason;
      } else if (!term?.exception_reference?.trim() || exceptionDates(term) !== dates || !form.exception_reference.trim()) {
        setPendingException({ payload, dates, messages });
        return;
      }
    }
    submit(payload);
  }}>
    {register || <h2 id="modal-title">{term ? 'Edit allotment / handover' : renewalOf ? 'Record approved renewal' : 'Record allotment'}</h2>}
    {contractEnabled && <div className="estate-form" onChangeCapture={() => setContractDirty(true)}>
    {canDraft && <button type="button" className="btn-ghost"
      onClick={() => setUnavailable(shownEssential)}>Mark all essential fields Not Available</button>}
    {renewalOf && <p className="payment-guidance">Keep the previous term in history. Confirm the new letter, dates, performance and approval references.</p>}
    <div className="estate-form-grid">
      {!register && <label htmlFor="term-tenant">Allottee<select id="term-tenant" className="inp" required value={form.tenant} disabled={Boolean(form.renewal_of)} onChange={e => set('tenant')(e.target.value)}>
        <option value="">Choose an allottee</option>{availableTenants.map(item => <option key={item.id} value={item.id}>{allotteeLabel(item)}</option>)}</select></label>}
      {premisesEnabled && <label htmlFor="term-shop">Premises (optional)
        <select id="term-shop" className="inp" value={shop} disabled={Boolean(renewalOf || premises.loading || premises.error)}
          onChange={event => setShop(event.target.value)}>
          <option value="">{premises.loading ? 'Loading premises…' : 'No premises link'}</option>
          {premises.rows.map(item => <option key={item.id} value={item.id}
            disabled={!item.active && String(shop) !== String(item.id)}>{item.code} — {item.name}</option>)}
        </select>
        {premises.error && <span role="alert">{premises.error}</span>}
      </label>}
      {additionalDetails && input('source_notice', 'Source notice (optional)')}
      <div className="estate-form-pair">
        {input('letter_issued_on', 'Letter issued on', { type: 'date', required: true })}
        {input('award_reference', 'Award / extension letter reference', { required: true })}
      </div>
      <div className="estate-form-pair">
        {input('start_date', 'Term start date', { type: 'date', required: true })}
        {input('end_date', 'Term end date (inclusive)', { type: 'date', required: true, min: form.start_date || undefined })}
      </div>
      <div className="estate-wide"><label htmlFor="term-rent-basis">Monthly charge basis
        <select id="term-rent-basis" className="inp" value={unavailable.includes('rent_basis') ? '' : form.rent_basis}
          disabled={Boolean(savedRate || form.renewal_of || unavailable.includes('rent_basis'))}
          onChange={event => { set('rent_basis')(event.target.value); setAmount(''); }}>
          {unavailable.includes('rent_basis') && <option value="">Not Available</option>}
          <option value="area">Area × accepted rate</option><option value="flat">Flat monthly charge</option>
        </select>
      </label>{availabilityBox('rent_basis', 'Monthly charge basis')}</div>
      {showArea && <div className="estate-form-pair">
        {input('actual_area', 'Actual allotted area (sq ft)', { type: 'number', min: '0.0001', step: '0.0001', required: true })}
        {additionalDetails && input('measurement_reference', 'Measurement reference')}
      </div>}
      {!form.renewal_of && <div className="estate-wide">
        <Field id="term-accepted-rate" label={amountLabel} disabled={unavailable.includes('accepted_rate_amount')}
          type="number" min={flat ? '0.01' : '0.0001'} step={flat ? '0.01' : '0.0001'}
          required={!term || flat} readOnly={Boolean(savedRate)} value={savedRate?.amount ?? amount} onChange={setAmount} />
        {availabilityBox('accepted_rate_amount', amountLabel)}
      </div>}
      {additionalDetails && !savedRate && !form.renewal_of && <div className="estate-form-pair">
        <Field id="term-rate-as-of" label="Accepted charge effective date (defaults to term start)" type="date"
          value={asOf} onChange={setAsOf} max={form.end_date || undefined} />
        {input('approved_rate_reference', 'Accepted charge approval reference')}
      </div>}
      {calculated && <p className="form-feedback estate-wide">Full-month charge {formatCurrency(calculated)}</p>}
      {form.renewal_of && input('performance_reference', 'Satisfactory performance reference', { required: true })}
      {form.renewal_of && input('approval_reference', 'Renewal approval reference', { required: true })}
      {form.renewal_of && <div className="estate-wide">
        <label className="estate-checkbox"><input type="checkbox" checked={form.carry_forward_deposit}
          onChange={event => set('carry_forward_deposit')(event.target.checked)} /> Carry forward existing security deposit</label>
        <p className="payment-guidance">Select if the allottee chooses to carry forward the deposit held under the original award.</p>
      </div>}
    </div>
    {additionalDetails && <details className="estate-form-section"><summary>More details</summary><div className="estate-form-grid">
      <div className="estate-form-pair">
        {input('possession_date', 'Possession date', { type: 'date' })}
        {input('possession_reference', 'Possession reference', { required: Boolean(form.possession_date) })}
      </div>
      <div className="estate-form-pair">
        {input('termination_date', 'Effective termination date', { type: 'date' })}
        {input('termination_reference', 'Termination order reference', { required: Boolean(form.termination_date) })}
      </div>
      <div className="estate-form-pair">
        {input('handover_date', 'Actual handover date', { type: 'date' })}
        {input('handover_reference', 'Handover evidence reference', { required: Boolean(form.handover_date) })}
      </div>
      <div className="estate-form-pair">
        {input('vacation_deadline', 'Approved alternative vacation deadline', { type: 'date' })}
        {input('vacation_reference', 'Alternative deadline reference', { required: Boolean(form.vacation_deadline) })}
      </div>
      <div className="estate-wide">{input('exception_reference', 'Approved date / duration exception reference')}</div>
      {(form.exception_reference || form.exception_reason) && <label className="estate-wide" htmlFor="term-exception-reason">Date exception reason
        <textarea id="term-exception-reason" className="inp" rows={3} maxLength={2000} value={form.exception_reason}
          onChange={event => set('exception_reason')(event.target.value)} />
      </label>}
    </div>
    </details>}
    <label htmlFor="term-notes">Contract notes<textarea id="term-notes" className="inp" value={form.notes} onChange={e => set('notes')(e.target.value)} /></label>
    {term && !register && input('change_reason', 'Reason for this change', { required: true, maxLength: 2000 })}
    </div>}
    <FormActions onClose={onClose} label={register ? (tenant ? 'Save Allotment' : 'Add Allotment') : term ? 'Save allotment' : renewalOf ? 'Record renewal' : 'Record allotment'} />
  </form>
  {pendingException && <DateExceptionDialog messages={pendingException.messages} reference={form.exception_reference} reason={form.exception_reason}
    onClose={() => setPendingException(null)} onConfirm={evidence => {
      setForm(previous => ({ ...previous, ...evidence }));
      setConfirmedDates(pendingException.dates);
      setPendingException(null);
      submit({ ...pendingException.payload, ...evidence });
    }} />}</>;
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

export function RentRevisionForm({ originalAward, rate, previousRate, flat, notice, onSave, onClose }) {
  const [form, setForm] = useState(() => initialValues({ effective_date: '', rate: '', approval_reference: '',
    reason: '', exception_reference: '', change_reason: '' }, rate));
  const [preview, setPreview] = useState({ busy:false, error:'', message:'' });
  const [dateMode, setDateMode] = useState('date');
  const effectiveDate = dateMode === 'month' && form.effective_date ? `${form.effective_date.slice(0, 7)}-01` : form.effective_date;
  const set = key => value => setForm(old => ({...old,[key]:value}));
  const calculate = async () => {
    const asOf = previousRate.effective_date;
    const year = Math.max(2026, Number(asOf.slice(0,4)) + (asOf.slice(5) >= '04-01' ? 1 : 0));
    setPreview({busy:true,error:'',message:''});
    try {
      const result = await API.get(`/rent-revisions/${previousRate.id}/annual-preview/?through=${effectiveDate || `${year}-04-01`}`);
      const next = result.revisions[0];
      if (next) setForm(old=>({...old, effective_date:next.effective_date, rate:next.rate}));
      setPreview({busy:false,error:'',message:next ? 'Proposed increase only. Record the actual approval before saving.' : 'No unapproved annual increase through that date.'});
    } catch(error) {setPreview({busy:false,error:error.message,message:''});}
  };
  return <form className="estate-form" aria-label="Reviewed rent rate" onSubmit={event=>{
    event.preventDefault(); if(!event.currentTarget.reportValidity()) return;
    onSave({ ...form, original_award: originalAward, effective_date: effectiveDate,
      reason: notice ? form.reason : form.reason.trim() || 'Rent rate recorded for billing.' });
  }}><h2 id="modal-title">{rate ? 'Correct rate evidence' : 'Add rent rate'}</h2>
    <div className="estate-form-grid">
      <label htmlFor="rate-effective-mode">Effective from
        <select id="rate-effective-mode" className="inp" value={dateMode} onChange={event => setDateMode(event.target.value)}>
          <option value="date">Specific date</option>
          <option value="month">Start of a month</option>
        </select>
      </label>
      <Field id="rate-effective" label={dateMode === 'month' ? 'Effective month' : 'Effective date'}
        type={dateMode} required value={dateMode === 'month' ? form.effective_date.slice(0, 7) : form.effective_date}
        onChange={value => set('effective_date')(dateMode === 'month' && value ? `${value}-01` : value)} />
      <Field id="rate-amount" label={flat ? 'Flat monthly charge (₹)' : 'Rate per sq ft per month (₹)'} type="number" min={flat ? '0.01' : '0.0001'} step={flat ? '0.01' : '0.0001'} required value={form.rate} onChange={set('rate')} />
      <Field id="rate-approval" label={notice ? 'Approval reference' : 'Approval reference (optional)'} required={notice} value={form.approval_reference} onChange={set('approval_reference')} maxLength={250} />
      <Field id="rate-reason" label={notice ? 'Reason / reviewed basis' : 'Reason (optional)'} required={notice} value={form.reason} onChange={set('reason')} />
      {notice && <Field id="rate-exception" label="Authorized exception reference, if applicable" value={form.exception_reference} onChange={set('exception_reference')} maxLength={250} />}
      {rate && <Field id="rate-change-reason" label="Reason for this change" required value={form.change_reason} onChange={set('change_reason')} maxLength={2000} />}
    </div>
    {notice && previousRate && !rate && <button type="button" className="btn-ghost" disabled={preview.busy} onClick={calculate}>{preview.busy ? 'Calculating…' : 'Preview 5% April increase'}</button>}
    {preview.error && <p role="alert">{preview.error}</p>}{preview.message && <p role="status">{preview.message}</p>}
    <FormActions onClose={onClose} label={rate ? 'Save rate evidence' : 'Save rent rate'} />
  </form>;
}

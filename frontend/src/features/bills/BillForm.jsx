import { allotteeLabel, formatCurrency } from "../../shared/format.js";
import { Fragment, useState, useEffect, useMemo } from "react";
import API from '../../api';
import { calculateFullMonthRent, RentEntryFields } from './RentEntryFields';
import './billing.css';

export function BillForm({ tenants, initialTenant, initialAllotment, onSave, onClose }) {
  const activeTenants = tenants.filter(t => t.active);
  const selectedTenant = activeTenants.some(t => String(t.id) === String(initialTenant)) ? initialTenant : activeTenants[0]?.id || "";
  const now = new Date();
  const currentPeriod = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [form, setForm] = useState({
    tenant: selectedTenant, from_period: currentPeriod, to_period: currentPeriod,
    rent: "", rent_method: "", rent_area: "", rent_rate: "", water: "", gst_treatment: "cgst_sgst", notes: "",
    billing_category: 'allotment', allotment: initialAllotment || '', holiday_start_date: '', holiday_end_date: '',
    raised_date: new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(now),
    rent_override_reason: '', rate_exception_reference: ''
  });
  const [terms, setTerms] = useState({ loading: true, error: '', rows: [] });
  const [preview, setPreview] = useState(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setTerms(old => ({ ...old, loading: true, error: '' }));
    API.getAll('/allotments/').then(rows => { if (active) setTerms({ loading: false, error: '', rows }); })
      .catch(error => { if (active) setTerms({ loading: false, error: error.message, rows: [] }); });
    return () => { active = false; };
  }, [retry]);
  const [electricRows, setElectricRows] = useState({});
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const parsePeriod = (value) => {
    const [year, month] = String(value || "").split("-").map(Number);
    return { year, month };
  };
  const from = parsePeriod(form.from_period);
  const to = parsePeriod(form.to_period);
  const monthCount = from.year && from.month && to.year && to.month
    ? Math.max(0, (to.year * 12 + to.month) - (from.year * 12 + from.month) + 1)
    : 0;
  const periods = useMemo(() => {
    if (monthCount < 1 || monthCount > 36) return [];
    const rows = [];
    for (let index = from.year * 12 + from.month; index <= to.year * 12 + to.month; index += 1) {
      const year = Math.floor((index - 1) / 12);
      const month = (index - 1) % 12 + 1;
      const key = `${year}-${String(month).padStart(2, "0")}`;
      const label = new Date(year, month - 1, 1).toLocaleString("en-IN", { month: "short", year: "numeric" });
      rows.push({ year, month, key, label });
    }
    return rows;
  }, [monthCount, from.month, from.year, to.month, to.year]);
  useEffect(() => {
    setElectricRows(prev => {
      const next = {};
      periods.forEach(p => {
        next[p.key] = prev[p.key] || { electric: "", electric_reading: "" };
      });
      return next;
    });
  }, [periods]);
  const setElectricRow = (key, field, value) => {
    setElectricRows(prev => ({
      ...prev,
      [key]: { ...(prev[key] || { electric: "", electric_reading: "" }), [field]: value }
    }));
  };
  const eligibleTerms = terms.rows.filter(term => String(term.tenant) === String(form.tenant)
    && term.start_date.slice(0, 7) <= form.from_period && (term.effective_end || term.end_date).slice(0, 7) >= form.to_period);
  const selectedTerm = eligibleTerms.find(term => String(term.id) === String(form.allotment))
    || (!form.allotment && eligibleTerms.length === 1 ? eligibleTerms[0] : null);
  const notice = form.billing_category === 'allotment' && selectedTerm?.notice_governed;
  const scheduleAvailable = notice || (form.billing_category === 'allotment' && Boolean(selectedTerm?.accepted_rate));
  const useApprovedRate = scheduleAvailable && (form.rent_method === 'approved' || (!form.rent_method && form.rent === ''));
  const rentMethod = form.rent_method === 'calculated' ? 'calculated' : useApprovedRate ? 'approved' : 'direct';
  const calculatedRent = rentMethod === 'calculated' ? calculateFullMonthRent(form.rent_area, form.rent_rate) : null;
  const fullRent = rentMethod === 'calculated' ? calculatedRent : form.rent;
  const monthItems = periods.map(p => ({
      month: p.month,
      year: p.year,
      electric: electricRows[p.key]?.electric || 0,
      electric_reading: electricRows[p.key]?.electric_reading || "",
    }));
  const payload = {
      tenant: form.tenant,
      billing_category: form.billing_category,
      allotment: form.billing_category === 'allotment' ? selectedTerm?.id || null : null,
      ...(notice ? { raised_date: form.raised_date || null, rent_override_reason: form.rent_override_reason,
        rate_exception_reference: form.rate_exception_reference } : {}),
      ...(rentMethod !== 'approved' ? { full_month_rent: fullRent || '0' } : {}),
      holiday_start_date: form.holiday_start_date || null,
      holiday_end_date: form.holiday_end_date || null,
      water: form.water || 0,
      gst_treatment: form.gst_treatment || "cgst_sgst",
      notes: form.notes || "",
    };
  const rangePayload = { ...payload, from_month: from.month, from_year: from.year,
    to_month: to.month, to_year: to.year, month_items: monthItems };
  const signature = JSON.stringify([rangePayload, rentMethod, rentMethod === 'calculated' && [form.rent_area, form.rent_rate]]);
  const valid = Boolean(form.tenant && monthCount >= 1 && monthCount <= 36
    && (form.billing_category === 'other' ? form.notes.trim() : selectedTerm && !terms.loading && !terms.error)
    && (rentMethod !== 'calculated' || calculatedRent !== null)
    && (rentMethod !== 'direct' || !scheduleAvailable || fullRent !== '')
    && ![rentMethod === 'approved' ? 0 : fullRent, form.water, ...monthItems.map(item => item.electric)]
      .some(value => !Number.isFinite(Number(value)) || Number(value) < 0)
    && Boolean(form.holiday_start_date) === Boolean(form.holiday_end_date)
    && (!form.holiday_start_date || form.holiday_end_date >= form.holiday_start_date));
  const currentPreview = preview?.signature === signature ? preview.months : null;
  const previewAmounts = async () => {
    if (!valid || previewing) return;
    setPreviewing(true); setPreviewError(''); setPreview(null);
    try {
      const result = await API.post('/bills/preview/', rangePayload);
      setPreview({ signature, months: result.months });
    } catch (error) { setPreviewError(error.message); }
    finally { setPreviewing(false); }
  };
  const submit = () => {
    if (!valid || !currentPreview?.some(row => !row.already_exists)) return;

    if (monthCount === 1) {
      onSave({ ...payload, ...monthItems[0] });
      return;
    }

    onSave({
      bulk: true,
      payload: rangePayload,
    });
  };

  return (
    <div style={{ width: 680, maxWidth: "100%" }}>
      <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>Raise Bill</h2>
      <div className="bill-form-grid">
        <div style={{ gridColumn: "1/-1" }}><label htmlFor="billform-tenant">Allottee</label><select id="billform-tenant" className="inp" value={form.tenant} onChange={e => setForm(old => ({ ...old, tenant: e.target.value, allotment: '' }))}>{activeTenants.map(t => <option key={t.id} value={t.id}>{allotteeLabel(t)}</option>)}</select></div>
        <div style={{ gridColumn: '1/-1' }}><label htmlFor="billform-category">Bill category</label><select className="inp" id="billform-category" value={form.billing_category} onChange={e => set('billing_category', e.target.value)}><option value="allotment">Allotment</option><option value="other">Other monthly charges</option></select></div>
        <div><label htmlFor="billform-from-month">From Month</label><input id="billform-from-month" className="inp" type="month" value={form.from_period} onChange={e => set("from_period", e.target.value)} /></div>
        <div><label htmlFor="billform-to-month">To Month</label><input id="billform-to-month" className="inp" type="month" value={form.to_period} onChange={e => set("to_period", e.target.value)} /></div>
        {form.billing_category === 'allotment' && <div style={{ gridColumn: '1/-1' }}><label htmlFor="billform-allotment">Allotment term</label><select className="inp" id="billform-allotment" value={selectedTerm?.id || ''} onChange={e => set('allotment', e.target.value)}><option value="">Choose a term</option>{eligibleTerms.map(term => <option key={term.id} value={term.id}>{term.award_reference || term.register_label || term.tenant_name} · {term.start_date} — {term.effective_end || term.end_date}</option>)}</select>
          {terms.loading ? <p role="status">Loading allotments…</p> : terms.error ? <div role="alert">{terms.error}<button className="btn-ghost" onClick={() => setRetry(n => n + 1)}>Retry allotments</button></div> : !eligibleTerms.length && <p>No allotment covers this billing range. Record or review the allotment term under Allotments.</p>}</div>}
        {form.billing_category === 'allotment' && form.allotment && !selectedTerm && !terms.loading && <p style={{gridColumn:'1/-1'}}>The selected allotment does not cover this range. Review the dates or explicitly choose another term.</p>}
        <RentEntryFields prefix="billform" method={rentMethod} form={form} directRent={form.rent} directField="rent"
          calculatedRent={calculatedRent} approved={scheduleAvailable} set={set} />
        {notice && <>
          <p style={{gridColumn:'1/-1',fontSize:12}}>The approved schedule uses the charge basis recorded for the allotment term. A different amount needs a reviewed reason. Leave raised date empty to prepare a draft.</p>
          <div><label htmlFor="billform-raised">Invoice raised date</label><input className="inp" id="billform-raised" type="date" value={form.raised_date} onChange={e => set('raised_date',e.target.value)} /></div>
          <div><label htmlFor="billform-rate-exception">Approved rate exception reference</label><input className="inp" id="billform-rate-exception" value={form.rate_exception_reference} onChange={e => set('rate_exception_reference',e.target.value)} /></div>
          <div style={{gridColumn:'1/-1'}}><label htmlFor="billform-rent-reason">Reason for a reviewed rent override</label><textarea className="inp" id="billform-rent-reason" value={form.rent_override_reason} onChange={e => set('rent_override_reason',e.target.value)} /></div>
        </>}
        <div><label htmlFor="billform-water">Water (₹)</label><input id="billform-water" className="inp" type="number" value={form.water} onChange={e => set("water", e.target.value)} /></div>
        <div><label htmlFor="billform-gst-type">GST Type</label><select id="billform-gst-type" className="inp" value={form.gst_treatment} onChange={e => set("gst_treatment", e.target.value)}><option value="cgst_sgst">CGST + SGST</option><option value="igst">IGST</option></select></div>
        <div style={{ gridColumn: '1/-1' }}><p>Optional holiday closure: both dates are included. Rent is waived for actual closure days in each month; utilities stay payable.</p></div>
        <div><label htmlFor="billform-holiday-start">Holiday start date</label><input className="inp" id="billform-holiday-start" type="date" value={form.holiday_start_date} onChange={e => set('holiday_start_date', e.target.value)} /></div>
        <div><label htmlFor="billform-holiday-end">Holiday end date</label><input className="inp" id="billform-holiday-end" type="date" value={form.holiday_end_date} onChange={e => set('holiday_end_date', e.target.value)} /></div>
        <div style={{ gridColumn: '1/-1' }}><label htmlFor="billform-notes">{form.billing_category === 'other' ? 'Reason for other monthly charge (required)' : 'Notes'}</label><textarea className="inp" id="billform-notes" value={form.notes} onChange={e => set('notes', e.target.value)} /></div>
        <p style={{ gridColumn: "1/-1", fontSize: 12, color: "#8b949e", marginTop: 8 }}>{notice ? 'Payment is due seven calendar days after raising. Late interest waits for confirmed email dispatch and the deadline. A draft has no finalized debt.' : 'The bill stays Pending Receipt with no late-payment penalty until receipt is confirmed through mail.'}</p>
        {monthCount > 0 && (
          <div style={{ gridColumn: "1/-1", border: "1px solid #30363d", borderRadius: 8, overflow: "hidden" }}>
            <div className="bill-electric-row bill-electric-heading" style={{ padding: "9px 12px", background: "#0d1117", color: "#8b949e", fontFamily: "'JetBrains Mono',monospace", fontSize: 11, textTransform: "uppercase" }}>
              <span>Month</span><span>Electric</span><span>Electricity Reading</span>
            </div>
            {periods.map(p => (
              <div key={p.key} className="bill-electric-row" style={{ alignItems: "center", padding: "10px 12px", borderTop: "1px solid #21262d" }}>
                <div style={{ color: "#f0a500", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>{p.label}</div>
                <input aria-label={`Electricity amount for ${p.label}`} className="inp" type="number" value={electricRows[p.key]?.electric || ""} onChange={e => setElectricRow(p.key, "electric", e.target.value)} />
                <input aria-label={`Electricity reading for ${p.label}`} className="inp" value={electricRows[p.key]?.electric_reading || ""} placeholder="e.g. Prev 1200, Current 1420, Units 220" onChange={e => setElectricRow(p.key, "electric_reading", e.target.value)} />
              </div>
            ))}
          </div>
        )}
        {monthCount > 1 && (
          <div style={{ gridColumn: "1/-1", background: "#0d1117", border: "1px solid #30363d", borderRadius: 8, padding: "10px 12px", color: "#f0a500", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            This will raise {monthCount} separate monthly bills. {rentMethod === 'approved' ? 'Approved rent is calculated for each month.' : 'The same full-month rent applies to each month.'} Holiday waivers and electricity are calculated separately for each month.
          </div>
        )}
        {monthCount === 0 && (
          <div style={{ gridColumn: "1/-1", background: "#ef444422", border: "1px solid #ef4444", borderRadius: 8, padding: "10px 12px", color: "#f87171", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            To Month must be the same as or after From Month.
          </div>
        )}
        {monthCount > 36 && (
          <div style={{ gridColumn: "1/-1", background: "#ef444422", border: "1px solid #ef4444", borderRadius: 8, padding: "10px 12px", color: "#f87171", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>
            Bulk bill creation is limited to 36 months at a time.
          </div>
        )}
      </div>
      <button className="btn-ghost" style={{ marginTop: 16 }} disabled={!valid || previewing} onClick={previewAmounts}>{previewing ? 'Calculating…' : 'Preview monthly amounts'}</button>
      {previewError && <p role="alert">{previewError}</p>}
      {currentPreview ? <BillPreviewTable months={currentPreview} />
        : <p role="status" style={{ fontSize: 12 }}>Preview the current amounts before raising bills.</p>}
      <div style={{ display: "flex", gap: 10, marginTop: 20, justifyContent: "flex-end" }}>
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={!valid || previewing || !currentPreview?.some(row => !row.already_exists)} onClick={submit}>Raise Bill</button>
      </div>
    </div>
  );
}

export function BillPreviewTable({ months, editing = false }) {
  return <div className="table-scroll bill-preview" role="region" aria-label="Monthly rent preview" tabIndex={0}>
    <table><thead><tr><th>Month</th><th>Full rent</th><th>Closed / days</th><th>Waiver</th><th>Net rent</th><th>GST</th><th>Total</th><th>Action</th></tr></thead>
      <tbody>{months.map(row => <Fragment key={`${row.year}-${row.month}`}><tr>
        <td>{row.month_name} {row.year}</td><td>{row.full_month_rent == null ? 'Not recorded' : formatCurrency(row.full_month_rent)}</td>
        <td>{row.holiday_closed_days} / {row.days_in_month}</td><td>{formatCurrency(row.holiday_waiver)}</td>
        <td>{formatCurrency(row.rent)}</td><td>{formatCurrency(row.gst_on_rent)}</td><td>{formatCurrency(row.total_amount)}</td>
        <td>{editing ? 'Update' : row.already_exists ? 'Already billed · skipped' : 'Create'}</td></tr>
        {row.billing_policy === 'notices_368_369' && <tr><td colSpan={8} className="bill-preview-evidence">
          {row.rate_snapshot ? row.area_snapshot
            ? `Rate ${row.rate_snapshot}/sq ft · area ${row.area_snapshot} · ${row.rent_revision_reference}`
            : `Flat monthly charge ${formatCurrency(row.rate_snapshot)} · ${row.rent_revision_reference}` : 'Rate schedule needs review.'}
          {' · '}{row.receipt_status}{row.due_date ? ` · Due ${row.due_date}` : ''}
          {row.rate_warnings?.map(warning => <div key={warning}>{warning}</div>)}</td></tr>}
        {row.previous_interest_accrued != null && <tr><td colSpan={8} className="bill-preview-evidence">
          Interest under the saved policy: {formatCurrency(row.previous_interest_accrued)} → {formatCurrency(row.interest_accrued)}.
          {' '}Receipts retained: principal {formatCurrency(row.principal_paid)}, interest {formatCurrency(row.interest_paid)}.
          {' '}Excess for review: principal {formatCurrency(row.excess_principal_paid)}, interest {formatCurrency(row.excess_interest_paid)}.
          {' '}No refund or receipt deletion is created.</td></tr>}
      </Fragment>)}</tbody></table>
  </div>;
}

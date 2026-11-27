import { useEffect, useState } from "react";
import API from "../../api";
import { AllotmentForm } from "../estate/EstateForms";
import { allotteeLabel } from "../../shared/format";

export function TenantStatusForm({ tenant, onSave, onClose }) {
  const [reason, setReason] = useState("");
  const action = tenant.active ? "Deactivate" : "Activate";
  return <form onSubmit={event => {
    event.preventDefault();
    if (reason.trim()) onSave({ active: !tenant.active, change_reason: reason.trim() });
  }}>
    <h2 id="modal-title">{action} allotment</h2>
    <p>{allotteeLabel(tenant)}</p>
    <label htmlFor="allotment-status-reason">Reason for status change</label>
    <textarea id="allotment-status-reason" className="inp" rows={3} required maxLength={2000}
      value={reason} onChange={event => setReason(event.target.value)} />
    <div className="estate-actions" style={{ justifyContent: "flex-end", marginTop: 16 }}>
      <button type="button" className="btn-ghost" onClick={onClose}>Cancel</button>
      <button type="submit" className="btn-primary" disabled={!reason.trim()}>{action} allotment</button>
    </div>
  </form>;
}

export function TenantForm({ tenant, premisesEnabled, additionalDetails, onOpenRentRates, onSave, onClose }) {
  const [form, setForm] = useState({
    name: tenant?.name || "",
    allotment_description: tenant?.allotment_description || "",
    type: tenant?.type || "",
    contact: tenant?.contact || "",
    contact_not_provided: tenant?.contact_not_provided || false,
    email: tenant?.email || "",
    email_not_provided: tenant?.email_not_provided || false,
    gstin: tenant?.gstin || "",
    gstin_not_provided: tenant?.gstin_not_provided || false,
    address: tenant?.address || "",
    address_not_provided: tenant?.address_not_provided || false,
    due_days: tenant?.due_days || 5,
    penalty_type: tenant?.penalty_type || "system",
    custom_penalty_rate: tenant?.custom_penalty_rate || "",
    custom_penalty_lumpsum: tenant?.custom_penalty_lumpsum || "",
    custom_penalty_frequency: tenant?.custom_penalty_frequency || "system"
  });
  const [history, setHistory] = useState({ loading: Boolean(tenant), error: "", rows: [] });
  const [profileDirty, setProfileDirty] = useState(false);
  const [retry, setRetry] = useState(0);
  const [includeContract, setIncludeContract] = useState(Boolean(tenant?.contract_draft?.unavailable?.length));
  useEffect(() => {
    if (!tenant) return;
    let active = true;
    setHistory(previous => ({ ...previous, loading: true, error: "" }));
    API.getAll(`/allotments/?tenant=${tenant.id}`).then(rows => {
      if (active) setHistory({ loading: false, error: "", rows });
    }).catch(error => {
      if (active) setHistory({ loading: false, error: error.message, rows: [] });
    });
    return () => { active = false; };
  }, [tenant, retry]);
  const current = history.rows.filter(term => term.status === "current");
  const candidates = current.length ? current : history.rows.filter(term => term.status === "future");
  const draft = tenant?.contract_draft?.unavailable?.length ? tenant.contract_draft : null;
  const contract = !draft && candidates.length === 1 ? candidates[0] : null;
  const canAddContract = tenant?.active !== false && (draft || candidates.length === 0) && !history.loading && !history.error;
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));
  const markNotProvided = (field, checked) => setForm(p => ({
    ...p, [`${field}_not_provided`]: checked, ...(checked ? { [field]: "" } : {})
  }));
  const optionalField = (field, label, input) => <div>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
      <label htmlFor={`tenant-${field}`}>{label}</label><label style={{ display: "flex", alignItems: "center", gap: 6, textTransform: "none", letterSpacing: 0 }}>
        <input type="checkbox" aria-label={`${label}: not provided`} checked={form[`${field}_not_provided`]} onChange={e => markNotProvided(field, e.target.checked)} />Not Provided
      </label>
    </div>
    {input(form[`${field}_not_provided`])}
  </div>;

  return (
    <AllotmentForm key={contract?.id || "new"} tenant={tenant?.id} term={contract} draft={draft} premisesEnabled={premisesEnabled} additionalDetails={additionalDetails}
      contractEnabled={Boolean(contract) || (canAddContract && includeContract)} onClose={onClose} onEdit={() => setProfileDirty(true)}
      onSave={details => onSave(details ? { ...form, contract: details } : form)} register={<>
      <h2 id="modal-title" style={{ fontSize: 24, fontWeight: 700, marginBottom: 20, paddingBottom: 14, borderBottom: "1px solid #21262d" }}>{tenant ? "Edit Allotment" : "Add Allotment"}</h2>
      {tenant && onOpenRentRates && <button type="button" className="btn-ghost" onClick={() => {
        if (!profileDirty || window.confirm('Discard unsaved allotment edits and open rent rates?')) onOpenRentRates(tenant);
      }}>Rent rates</button>}
      <div style={{ display: "grid", gap: 14 }}>
        <div><label htmlFor="tenantform-name">Allottee name</label><input id="tenantform-name" className="inp" value={form.name} onChange={e => set("name", e.target.value)} /></div>
        <div><label htmlFor="tenantform-description">Allotment description (optional)</label><input id="tenantform-description" className="inp" maxLength={200} placeholder="e.g. Shop 12, Market Block" value={form.allotment_description} onChange={e => set("allotment_description", e.target.value)} /><p className="form-feedback">Shown beside the name to distinguish separate allotments.</p></div>
        <div><label htmlFor="tenantform-type">Type</label><input id="tenantform-type" className="inp" maxLength={50} value={form.type} onChange={e => set("type", e.target.value)} /></div>
        {optionalField("contact", "Contact", notProvided => <input id="tenant-contact" className="inp" disabled={notProvided} value={form.contact} onChange={e => set("contact", e.target.value)} />)}
        {optionalField("email", "Email", notProvided => <input id="tenant-email" className="inp" type="email" disabled={notProvided} value={form.email} onChange={e => set("email", e.target.value)} />)}
        {optionalField("gstin", "GSTIN", notProvided => <input id="tenant-gstin" className="inp" maxLength={15} disabled={notProvided} value={form.gstin} onChange={e => set("gstin", e.target.value.toUpperCase())} />)}
        <details><summary>Billing settings</summary><div style={{ display: "grid", gap: 14 }}>
        <div><label htmlFor="tenantform-due-days-from-issue">Payment Period After Confirmed Receipt</label><input id="tenantform-due-days-from-issue" className="inp" readOnly value="5 calendar days" /></div>
        <div><label htmlFor="tenantform-penalty-type">Penalty Type</label><select id="tenantform-penalty-type" className="inp" value={form.penalty_type} onChange={e => setForm(p => ({ ...p, penalty_type: e.target.value, custom_penalty_rate: e.target.value === "percentage" ? p.custom_penalty_rate : "", custom_penalty_lumpsum: e.target.value === "lumpsum" ? p.custom_penalty_lumpsum : "", custom_penalty_frequency: ["system", "none"].includes(e.target.value) ? "system" : p.custom_penalty_frequency }))}><option value="system">System Default</option><option value="percentage">Percentage</option><option value="lumpsum">Lumpsum</option><option value="none">No Penalty</option></select></div>
        <div><label htmlFor="tenantform-penalty-rate">Penalty Rate (%)</label><input id="tenantform-penalty-rate" className="inp" type="number" value={form.custom_penalty_rate} onChange={e => setForm(p => ({ ...p, custom_penalty_rate: e.target.value, custom_penalty_lumpsum: e.target.value ? "" : p.custom_penalty_lumpsum, penalty_type: e.target.value ? "percentage" : p.penalty_type }))} /></div>
        <div><label htmlFor="tenantform-lumpsum-penalty">Lumpsum Penalty</label><input id="tenantform-lumpsum-penalty" className="inp" type="number" value={form.custom_penalty_lumpsum} onChange={e => setForm(p => ({ ...p, custom_penalty_lumpsum: e.target.value, custom_penalty_rate: e.target.value ? "" : p.custom_penalty_rate, penalty_type: e.target.value ? "lumpsum" : p.penalty_type }))} /></div>
        <div><label htmlFor="tenantform-penalty-frequency">Penalty Frequency</label><select id="tenantform-penalty-frequency" className="inp" value={form.custom_penalty_frequency} onChange={e => set("custom_penalty_frequency", e.target.value)}><option value="system">System Default</option><option value="day">Per Day</option><option value="month">Per Month</option><option value="year">Per Year</option></select></div>
        </div></details>
        {optionalField("address", "Address", notProvided => <textarea id="tenant-address" className="inp" rows={3} disabled={notProvided} value={form.address} onChange={e => set("address", e.target.value)} />)}
      </div>
      <section aria-label="Contract details">
        <h3>Contract details</h3>
        {history.loading && <p role="status">Loading contract details…</p>}
        {history.error && <div role="alert">{history.error} <button type="button" className="btn-ghost"
          onClick={() => setRetry(value => value + 1)}>Retry contract details</button></div>}
        {draft && <p role="status">Contract incomplete. Record the missing details when available.</p>}
        {!draft && candidates.length > 1 && <p>Open View term history to choose the contract you want to edit.</p>}
        {canAddContract && <label className="estate-checkbox">
          <input type="checkbox" checked={includeContract} onChange={event => setIncludeContract(event.target.checked)} /> Include contract details
        </label>}
      </section>
    </>} />
  );
}

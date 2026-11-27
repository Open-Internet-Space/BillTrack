import { allotteeLabel } from "../../shared/format.js";
import { useEffect, useRef, useState } from "react";
import API from "../../api";
import "./email-drafts.css";

const warning = "Review the recipients and amounts, then open the draft in Gmail or copy it into your mailbox.";

function gmailComposeUrl(draft, includeBody = true) {
  const addresses = value => (value || "").split(/[,;]/).map(address => address.trim()).filter(Boolean);
  const to = addresses(draft.to).map(address => encodeURIComponent(address).replace(/%40/g, "@")).join(",");
  const headers = new URLSearchParams({
    cc: addresses(draft.cc).join(","),
    bcc: addresses(draft.bcc).join(","),
    subject: draft.subject,
  });
  if (includeBody) headers.set("body", draft.body.replace(/\r\n|\r|\n/g, "\r\n"));
  const mailto = `mailto:${to}?${headers.toString().replace(/\+/g, "%20")}`;
  return `https://mail.google.com/mail/?extsrc=mailto&url=${encodeURIComponent(mailto)}`;
}

export function EmailDrafts({ context, tenants, onDirty, onBusy }) {
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState("");
  const [allottee, setAllottee] = useState(context?.allotteeId || "");
  const [bills, setBills] = useState([]);
  const [selected, setSelected] = useState(context?.billIds || []);
  const [draft, setDraft] = useState(null);
  const [dirty, setDirty] = useState(false);
  const [needsGeneration, setNeedsGeneration] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [templateReload, setTemplateReload] = useState(0);
  const [billReload, setBillReload] = useState(0);
  const [billError, setBillError] = useState("");
  const [loadingBills, setLoadingBills] = useState(false);
  const selectionLoaded = useRef(false);
  const selectedTemplate = templates.find(item => String(item.id) === String(template));

  useEffect(() => { onDirty(dirty); return () => onDirty(false); }, [dirty, onDirty]);
  useEffect(() => { onBusy(busy); return () => onBusy(false); }, [busy, onBusy]);
  useEffect(() => {
    const warn = event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    let active = true;
    API.get("/email-templates/").then(choices => {
      if (!active) return;
      setTemplates(choices);
      setTemplate(previous => choices.some(item => String(item.id) === String(previous)) ? previous : choices[0]?.id || "");
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, [templateReload]);
  useEffect(() => {
    if (!allottee) { setBills([]); return; }
    let active = true;
    setLoadingBills(true); setBillError("");
    API.getAll(`/bills/?tenant=${allottee}`).then(rows => {
      if (!active) return;
      setBills(rows);
      if (!selectionLoaded.current) {
        const explicit = Number(context?.allotteeId) === Number(allottee) ? context?.billIds : null;
        setSelected(explicit || rows.filter(bill => Number(bill.balance_due) + Number(bill.penalty) > 0).map(bill => bill.id));
        selectionLoaded.current = true;
      }
    }).catch(err => { if (active) setBillError(err.message); })
      .finally(() => { if (active) setLoadingBills(false); });
    return () => { active = false; };
  }, [allottee, context, billReload]);

  const mayDiscard = () => !dirty || window.confirm("Discard this temporary email and its case-specific edits? Saved templates will remain unchanged.");
  const chooseAllottee = value => {
    if (!mayDiscard()) return;
    selectionLoaded.current = false;
    setAllottee(value); setSelected([]); setDraft(null); setDirty(false); setNeedsGeneration(false); setNotice("");
  };
  const generate = async () => {
    if (busy) return;
    if (draft && !window.confirm("Replace this temporary email with current records and template defaults? Copy any case-specific edits you want to keep first.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const generated = await API.post("/email-drafts/generate/", { allottee_id: Number(allottee), bill_ids: selected, template_id: Number(template) });
      setDraft(generated); setDirty(true); setNeedsGeneration(false);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  };
  const copy = async (field, label) => {
    const input = document.getElementById(`draft-${field}`);
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(draft[field]); setNotice(`${label} copied.`);
    } catch {
      input?.focus(); input?.select();
      setNotice(`Select and copy ${label} using Ctrl+C or your device's Copy command.`);
    }
  };
  const change = (field, value) => { setDraft(previous => ({ ...previous, [field]: value })); setDirty(true); };
  const changeSelection = ids => { setSelected(ids); if (draft) { setDirty(true); setNeedsGeneration(true); } };
  const missing = selected.filter(id => !bills.some(bill => bill.id === id));
  const gmailUrl = draft && !needsGeneration && !busy && draft.to.trim() ? gmailComposeUrl(draft) : "";
  const bodyTooLong = gmailUrl.length > 8000;

  return <section className="email-drafts" aria-busy={busy}>
    <div className="page-toolbar"><h1 className="page-title">Email Drafts</h1></div>
    <p className="draft-warning">{warning}</p>
    <p>Saved templates work like Mail Merge: choose a template, then fill it with an allottee's details. Generated emails and case-specific edits are temporary and are never saved against an allottee.</p>
    <p>Administrators manage reusable wording in Admin → Email templates, and default CC addresses in System Settings.</p>
    {error && <p role="alert" className="error-message">{error} Your current text remains available.</p>}
    {notice && <p role="status" className="draft-notice">{notice}</p>}
    <fieldset disabled={busy} className="draft-fields">
      <legend className="draft-section-title">Merge a saved template</legend>
      <div className="draft-options">
        <label htmlFor="draft-template">Saved template<select id="draft-template" className="inp" value={template} onChange={event => {
          setTemplate(event.target.value); if (draft) { setDirty(true); setNeedsGeneration(true); }
        }}><option value="">Choose template</option>{templates.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
        <label htmlFor="draft-allottee">Fill details from allottee<select id="draft-allottee" className="inp" value={allottee} onChange={event => chooseAllottee(event.target.value)}><option value="">Choose allottee</option>{tenants.map(item => <option value={item.id} key={item.id}>{allotteeLabel(item)}</option>)}</select></label>
      </div>
      <button className="btn-ghost" onClick={() => { setError(""); setTemplateReload(value => value + 1); }}>Reload templates</button>
      {!templates.length && <p>No active templates loaded. Ask an administrator to configure templates, or reload after a connection problem.</p>}
      {selectedTemplate && <details className="draft-template-preview"><summary>Saved template wording (before merge)</summary><p>{selectedTemplate.subject}</p><pre>{selectedTemplate.body}</pre></details>}
      {loadingBills && <p role="status">Loading bills…</p>}
      {billError && <div role="alert" className="error-message"><p>{billError}</p><button className="btn-ghost" onClick={() => setBillReload(value => value + 1)}>Retry bills</button></div>}
      {allottee && !loadingBills && !billError && <fieldset className="draft-bill-picker"><legend>Include bills ({selected.length} selected)</legend>
        {!bills.length && <p>No bills found. You can prepare a general email without bills.</p>}
        {bills.map(bill => <label key={bill.id}><input type="checkbox" checked={selected.includes(bill.id)} onChange={event => changeSelection(event.target.checked ? [...selected, bill.id] : selected.filter(id => id !== bill.id))} /><span>{bill.month_name} {bill.year} · {bill.dispatch_ref_no || bill.invoice_no} · Outstanding INR {(Number(bill.balance_due) + Number(bill.penalty)).toFixed(2)}{!bill.issue_date ? " · Receipt not confirmed" : ""}</span></label>)}
        {missing.map(id => <label key={id}><input type="checkbox" checked onChange={() => changeSelection(selected.filter(pk => pk !== id))} />Unavailable bill {id} — remove before merging</label>)}
      </fieldset>}
      <button className="btn-ghost" disabled={!allottee || !template || loadingBills || Boolean(billError)} onClick={generate}>{draft ? "Refresh from current records" : "Generate Draft"}</button>
      {needsGeneration && <p role="status">Selection changed. Refresh from current records to merge the new selection.</p>}
      {draft && <div className="draft-editor">
        <p>Amounts captured: {new Date(draft.calculated_at).toLocaleString()}. Review current amounts before sending.</p>
        {!draft.to.trim() && <p role="alert">The To address is missing. Enter the vendor's address before sending from your mailbox.</p>}
        {gmailUrl && <>
          <a className="btn-primary gmail-compose" href={bodyTooLong ? gmailComposeUrl(draft, false) : gmailUrl}
            target="_blank" rel="noopener noreferrer">Open in Gmail</a>
          <p>{bodyTooLong ? "Use Copy Body and paste the message in Gmail, then attach the signed bill." : "Attach the signed bill in Gmail before sending."}</p>
        </>}
        {[["to", "To"], ["cc", "CC"], ["bcc", "BCC"], ["subject", "Subject"], ["body", "Body"]].map(([field, label]) => <div className="draft-email-field" key={field}>
          <div className="draft-field-heading"><label htmlFor={`draft-${field}`}>{label}</label><button type="button" className="btn-ghost" disabled={needsGeneration} onClick={() => copy(field, label)}>Copy {label}</button></div>
          {field === "body" ? <textarea id={`draft-${field}`} className="inp" rows={18} maxLength={100000} value={draft[field]} onChange={event => change(field, event.target.value)} /> : <input id={`draft-${field}`} className="inp" type="text" maxLength={field === "subject" ? 240 : 2000} value={draft[field] || ""} onChange={event => change(field, event.target.value)} />}
        </div>)}
        <p>Temporary email only. Editing this text does not change the saved template.</p>
      </div>}
    </fieldset>
    {busy && <p role="status">Merging current details… Please wait.</p>}
  </section>;
}

import { useEffect, useState } from 'react';
import API from '../../api';
import { formatCurrency, formatDate } from '../../shared/format';
import { Field, FormActions } from './EstateForms';

const kinds = {extension_fee:'Extension fee',incident_fine:'Incident fine',damage_recovery:'Damage recovery'};
const today = () => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());

export function EstateCharges({term,revision,setModal,user,initialCharge}) {
  const [state,setState]=useState({loading:true,rows:[],error:''});
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true;
    setState(old=>({...old,loading:true,error:''}));
    API.getAll(`/estate-charges/?allotment=${term.id}`).then(rows=>{if(active)setState({loading:false,rows,error:''});})
      .catch(error=>{if(active)setState(old=>({...old,loading:false,error:error.message}));});
    return ()=>{active=false;};
  },[term.id,revision,retry]);
  return <section aria-label="One-off charges">
    <div className="estate-toolbar"><h3>One-off charges and receipts</h3><div className="estate-actions">
      <button className="btn-ghost" onClick={()=>setModal({type:'estateCharge',term})}>Assess charge</button>
      {term.extension_number<2 && !state.loading && !state.error && !state.rows.some(row=>row.kind==='extension_fee') && <button className="btn-ghost" onClick={()=>setModal({type:'estateCharge',term,kind:'extension_fee'})}>Assess extension fee</button>}
    </div></div>
    {term.renewal_fee_settled===false && <p className="payment-guidance">Settle the assessed extension fee before recording an approved renewal.</p>}
    {state.loading ? <p role="status">Loading charges…</p> : state.error ? <div role="alert">{state.error}<button className="btn-ghost" onClick={()=>setRetry(n=>n+1)}>Retry charges</button></div>
      : state.rows.length ? state.rows.map(charge=><details key={charge.id} open={initialCharge===charge.id || undefined} className="card">
        <summary>{kinds[charge.kind]} · {charge.authority_reference} · Due {formatDate(charge.due_date)} · Balance {formatCurrency(charge.balance_due)}</summary>
        <p>{charge.description}</p><p>Assessed {formatCurrency(charge.gross_amount)} (tax {formatCurrency(charge.tax_amount)}) · Received {formatCurrency(charge.amount_paid)} · Waived {formatCurrency(charge.waiver_amount)} · {charge.status}</p>
        {charge.waiver_reference && <p>Waiver: {charge.waiver_reference} · {charge.waiver_reason}</p>}
        <div className="estate-actions">{Number(charge.balance_due)>0 && <button className="btn-primary" onClick={()=>setModal({type:'estateChargePayment',charge})}>Record charge receipt</button>}
          {user?.is_superuser && <><button className="btn-ghost" onClick={()=>setModal({type:'estateChargeDecision',charge,action:'waiver'})}>Review waiver</button><button className="btn-ghost" onClick={()=>setModal({type:'estateChargeDecision',charge,action:'assessment'})}>Correct assessment</button></>}</div>
        <ul className="estate-history">{charge.payments.map(payment=><li key={payment.id}><span>{formatDate(payment.payment_date)} · {payment.receipt_reference} · {formatCurrency(payment.amount)} · {payment.source==='receipt'?'Receipt':'Security application'} · {payment.recorded_by_name}</span>
          {payment.source==='receipt' && <button className="btn-ghost" onClick={()=>setModal({type:'estateChargePayment',charge,data:payment})}>Correct receipt</button>}</li>)}</ul>
      </details>) : <p>No one-off charges assessed for this term.</p>}
  </section>;
}

export function ChargeForm({term,kind,onSave,onClose}) {
  const [form,setForm]=useState({allotment:term.id,kind:kind||'incident_fine',description:'',net_amount:kind==='extension_fee'&&term.notice_governed?'1000':'',tax_amount:'',assessed_on:today(),due_date:today(),authority_reference:''});
  const set=key=>value=>setForm(old=>({...old,[key]:value}));
  return <form className="estate-form" aria-label="Charge assessment" onSubmit={event=>{event.preventDefault();if(event.currentTarget.reportValidity())onSave(form);}}>
    <h2 id="modal-title">Assess {kind==='extension_fee'?'extension fee':'charge'} · {term.shop_code}</h2>
    <p className="payment-guidance">Record the approved amount and tax explicitly, including zero tax. These charges do not accrue automatic interest.</p>
    <div className="estate-form-grid">
      {!kind && <label>Charge type<select className="inp" value={form.kind} onChange={event=>set('kind')(event.target.value)}><option value="incident_fine">Incident fine</option><option value="damage_recovery">Damage recovery</option></select></label>}
      <Field id="charge-description" label="Description" value={form.description} onChange={set('description')} required />
      <Field id="charge-net" label="Net assessment (₹)" type="number" min="0" step="0.01" value={form.net_amount} onChange={set('net_amount')} readOnly={kind==='extension_fee'&&term.notice_governed} required />
      <Field id="charge-tax" label="Approved tax (₹, enter 0 when applicable)" type="number" min="0" step="0.01" value={form.tax_amount} onChange={set('tax_amount')} required />
      <Field id="charge-assessed" label="Assessment date" type="date" max={today()} value={form.assessed_on} onChange={set('assessed_on')} required />
      <Field id="charge-due" label="Due date" type="date" min={form.assessed_on} value={form.due_date} onChange={set('due_date')} required />
      <Field id="charge-authority" label="Approval / assessment reference" maxLength={250} value={form.authority_reference} onChange={set('authority_reference')} required />
    </div><FormActions onClose={onClose} label="Save assessment" />
  </form>;
}

export function ChargePaymentForm({charge,payment,onSave,onClose}) {
  const [form,setForm]=useState({charge:charge.id,amount:payment?.amount||'',payment_date:payment?.payment_date||today(),receipt_reference:payment?.receipt_reference||'',notes:payment?.notes||'',...(payment?{change_reason:''}:{})});
  const set=key=>value=>setForm(old=>({...old,[key]:value}));
  return <form className="estate-form" aria-label="Charge receipt" onSubmit={event=>{event.preventDefault();if(event.currentTarget.reportValidity())onSave(form);}}>
    <h2 id="modal-title">{payment?'Correct':'Record'} charge receipt · {charge.shop_code}</h2><p>Balance {formatCurrency(charge.balance_due)} · {charge.authority_reference}</p>
    <div className="estate-form-grid">
      <Field id="charge-payment-amount" label="Amount received (₹)" type="number" min="0.01" step="0.01" value={form.amount} onChange={set('amount')} required />
      <Field id="charge-payment-date" label="Actual receipt date" type="date" min={charge.assessed_on} max={today()} value={form.payment_date} onChange={set('payment_date')} required />
      <Field id="charge-payment-reference" label="Receipt / DD reference" maxLength={250} value={form.receipt_reference} onChange={set('receipt_reference')} required />
      <Field id="charge-payment-notes" label="Notes" value={form.notes} onChange={set('notes')} />
      {payment && <Field id="charge-payment-reason" label="Reason for correction" value={form.change_reason} onChange={set('change_reason')} required />}
    </div><FormActions onClose={onClose} label="Save receipt" />
  </form>;
}

export function ChargeDecisionForm({charge,action,onSave,onClose}) {
  const [form,setForm]=useState({action,reference:'',reason:'',...(action==='waiver'?{waiver_amount:charge.waiver_amount}:{net_amount:charge.net_amount,tax_amount:charge.tax_amount})});
  const [preview,setPreview]=useState(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const signature=JSON.stringify(form);
  const set=key=>value=>{setForm(old=>({...old,[key]:value}));setPreview(null);};
  return <form className="estate-form" aria-label="Charge financial decision" onSubmit={async event=>{
    event.preventDefault();if(!event.currentTarget.reportValidity()||busy)return;
    setBusy(true);setError('');
    try {const result=await API.post(`/estate-charges/${charge.id}/decision-preview/`,form);setPreview({...result,signature});}
    catch(error){setError(error.message);}finally{setBusy(false);}
  }}>
    <h2 id="modal-title">Review {action==='waiver'?'waiver':'assessment correction'}</h2>
    <p className="payment-guidance">Recorded receipts remain in history. Approval applies only to the reviewed balance and expires after ten minutes.</p>
    <div className="estate-form-grid">
      {(action==='waiver'?['waiver_amount']:['net_amount','tax_amount']).map(key=><Field key={key} id={`decision-${key}`} label={key==='waiver_amount'?'Total cumulative waiver (₹)':key==='net_amount'?'Revised net amount (₹)':'Revised tax (₹)'} type="number" min="0" step="0.01" value={form[key]} onChange={set(key)} required />)}
      <Field id="decision-reference" label="Approval reference" maxLength={250} value={form.reference} onChange={set('reference')} required />
      <Field id="decision-reason" label="Reason for decision" maxLength={2000} value={form.reason} onChange={set('reason')} required />
    </div>{error && <p role="alert">{error}</p>}
    {preview?.signature===signature && <div className="card" role="status"><p>Assessment: {formatCurrency(preview.before.gross_amount)} → {formatCurrency(preview.after.gross_amount)}</p><p>Waiver: {formatCurrency(preview.before.waiver_amount)} → {formatCurrency(preview.after.waiver_amount)}</p><p>Balance: {formatCurrency(preview.before.balance_due)} → {formatCurrency(preview.after.balance_due)}</p><button type="button" className="btn-primary" onClick={()=>onSave({confirmation:preview.confirmation})}>Confirm reviewed decision</button></div>}
    <div className="estate-form-actions"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" type="submit" disabled={busy}>{busy?'Reviewing…':'Preview decision'}</button></div>
  </form>;
}

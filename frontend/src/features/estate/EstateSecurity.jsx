import { useEffect, useState } from 'react';
import API from '../../api';
import { formatCurrency, formatDate } from '../../shared/format';
import { Field, FormActions } from './EstateForms';

const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kolkata',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const actionLabel={requirement:'Review security requirement',apply_bill:'Apply security to bill',apply_charge:'Apply security to charge',refund:'Record reviewed refund',forfeit:'Record approved forfeiture'};
const timingLabel = { before: 'Before allotment order', after: 'After allotment order' };

export function EstateSecurity({originalAward,term,chain,revision,setModal,user}) {
  const [state,setState]=useState({loading:true,account:null,error:''});
  const [retry,setRetry]=useState(0);
  useEffect(()=>{
    let active=true;
    setState(old=>({...old,loading:true,error:''}));
    API.get(`/estate-security/${originalAward}/`).then(account=>{
      if(!account?.id)throw new Error('Could not read the deposit account. Refresh and try again.');
      if(active)setState({loading:false,account,error:''});
    }).catch(error=>{if(active)setState(old=>({...old,loading:false,error:error.message}));});
    return()=>{active=false;};
  },[originalAward,revision,retry]);
  const account=state.account;
  return <section className="estate-detail" aria-label="Security deposit">
    <div className="estate-toolbar"><h3>Security deposit · original award</h3>{account&&!state.loading&&!state.error&&<button className="btn-ghost" onClick={()=>setModal({type:'securityReceipt',account})}>Record deposit receipt</button>}</div>
    {state.loading?<p role="status">Loading security deposit…</p>:state.error?<div role="alert"><p>{state.error}</p><button className="btn-ghost" onClick={()=>setRetry(n=>n+1)}>Retry security account</button></div>:<>
      <p className="payment-guidance">This deposit belongs to the original award and its renewals. It is a liability, separate from rent collections. Actions record evidence and do not transfer money.</p>
      <dl className="estate-facts">
        <div><dt>Approved requirement</dt><dd>{account.required_amount===null?'Not reviewed':formatCurrency(account.required_amount)} · {account.requirement_reference||'No approval recorded'}</dd></div>
        <div><dt>Deposit timing</dt><dd>{timingLabel[account.timing] || 'Not recorded'}</dd></div>
        {account.offer_date && <div><dt>Offer of allotment date</dt><dd>{formatDate(account.offer_date)}</dd></div>}
        <div><dt>Deposit deadline</dt><dd>{formatDate(account.effective_due_date)}{account.extended_due_date&&` · Extension: ${account.extension_reference}`}</dd></div>
        <div><dt>Received / requirement still due</dt><dd>{formatCurrency(account.received)} / {formatCurrency(account.outstanding_requirement)}</dd></div>
        <div><dt>Currently held</dt><dd>{formatCurrency(account.held)}</dd></div>
        {term?.renewal_of && <div><dt>Deposit carry-forward for this extension</dt><dd>{term.carry_forward_deposit ? 'Recorded' : 'Not recorded'}</dd></div>}
        <div><dt>Refunded / applied / forfeited</dt><dd>{formatCurrency(account.refunded)} / {formatCurrency(account.applied)} / {formatCurrency(account.forfeited)}</dd></div>
        <div><dt>Refund review deadline / state</dt><dd>{formatDate(account.refund_review_due)} · {account.refund_review_status} · {account.refund_review_reference||'No clearance recorded'}</dd></div>
      </dl>
      {account.clearance_issues?.length>0&&<details><summary>Matters requiring clearance before a normal refund ({account.clearance_issues.length})</summary><ul>{account.clearance_issues.map((issue,index)=><li key={index}>{issue}</li>)}</ul></details>}
      {user?.is_superuser&&<div className="estate-actions">{Object.entries(actionLabel).map(([action,label])=><button key={action} className="btn-ghost" disabled={action!=='requirement'&&Number(account.held)<=0} onClick={()=>setModal({type:'securityDecision',account,action,chain})}>{label}</button>)}</div>}
      {account.movements.length?<ul className="estate-history">{account.movements.map(movement=><li key={movement.id}><span>{formatDate(movement.effective_date)} · {movement.kind} · {formatCurrency(movement.amount)} · {movement.reference} · {movement.recorded_by_name}<small>{movement.reason}{movement.operation_id&&` · Operation ${movement.operation_id}`}</small></span></li>)}</ul>:<p>No security receipts or movements recorded.</p>}
    </>}
  </section>;
}

export function SecurityReceiptForm({account,onSave,onClose}) {
  const [form,setForm]=useState({original_award:account.id,amount:'',effective_date:today(),reference:'',reason:''});
  const set=key=>value=>setForm(old=>({...old,[key]:value}));
  return <form className="estate-form" aria-label="Security deposit receipt" onSubmit={event=>{event.preventDefault();if(event.currentTarget.reportValidity())onSave(form);}}>
    <h2 id="modal-title">Record deposit receipt · {account.register_label}</h2>
    <p className="payment-guidance">Enter the actual receipt or DD evidence. This adds held security and does not pay a rent bill. Check existing movements before retrying an uncertain save.</p>
    <div className="estate-form-grid">
      <Field id="security-receipt-amount" label="Deposit actually received (₹)" type="number" min="0.01" step="0.01" value={form.amount} onChange={set('amount')} required />
      <Field id="security-receipt-date" label="Actual receipt date" type="date" max={today()} value={form.effective_date} onChange={set('effective_date')} required />
      <Field id="security-receipt-reference" label="Actual receipt / DD reference" maxLength={250} value={form.reference} onChange={set('reference')} required />
      <Field id="security-receipt-reason" label="Receipt evidence / reason" maxLength={2000} value={form.reason} onChange={set('reason')} required />
    </div><FormActions onClose={onClose} label="Save deposit receipt" />
  </form>;
}

export function SecurityDecisionForm({account,action,chain,onSave,onClose}) {
  const [form,setForm]=useState({action,reference:'',reason:'',...(action==='requirement'?{
    initial_monthly_rent:account.initial_monthly_rent||'',required_amount:account.required_amount||'',
    timing: account.timing || (account.required_amount == null ? 'before' : ''), offer_date: account.offer_date || '',
    pre_order_due_date: account.timing === 'before' ? account.due_date || '' : '',
    extended_due_date:account.extended_due_date||'',extension_reference:account.extension_reference||''
  }:{amount:'',effective_date:today(),...(action==='apply_bill'?{bill:'',interest_amount:'0'}:{}),
    ...(action==='apply_charge'?{charge:''}:{}),...(action==='refund'?{exception_reference:''}:{})})});
  const [obligations,setObligations]=useState({loading:['apply_bill','apply_charge'].includes(action),rows:[],error:''});
  const [retry,setRetry]=useState(0);
  const [preview,setPreview]=useState(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{
    if(!['apply_bill','apply_charge'].includes(action))return;
    let active=true;setObligations(old=>({...old,loading:true,error:''}));
    API.getAll(action==='apply_bill'?`/bills/?tenant=${account.tenant}`:`/estate-charges/?allotment__tenant=${account.tenant}`).then(rows=>{if(active)setObligations({loading:false,rows,error:''});})
      .catch(error=>{if(active)setObligations(old=>({...old,loading:false,error:error.message}));});
    return()=>{active=false;};
  },[action,account.tenant,retry]);
  const chainIds=chain.map(term=>term.id);
  const targets=obligations.rows.filter(row=>chainIds.includes(row.allotment)&&!row.is_draft&&Number(row.balance_due)+(action==='apply_bill'?Number(row.penalty||0):0)>0);
  const signature=JSON.stringify(form);
  const set=key=>value=>{setForm(old=>({...old,[key]:value}));setPreview(null);};
  const input=(key,label,props={})=><Field id={`security-${key.replaceAll('_','-')}`} label={label} value={form[key]} onChange={set(key)} {...props} />;
  return <form className="estate-form" aria-label="Security financial decision" onSubmit={async event=>{
    event.preventDefault();if(busy||!event.currentTarget.reportValidity())return;
    setBusy(true);setError('');
    const data={...form};
    if(action==='requirement'){
      if(!data.required_amount)delete data.required_amount;
      if(!data.timing)delete data.timing;
      if(data.timing === 'before'){
        data.offer_date = data.offer_date || null;
        data.pre_order_due_date = data.pre_order_due_date || null;
      }else{
        delete data.offer_date;
        delete data.pre_order_due_date;
      }
      data.extended_due_date=data.extended_due_date||null;
    }
    try{const result=await API.post(`/estate-security/${account.id}/decision-preview/`,data);setPreview({...result,signature});}
    catch(error){setError(error.message);}finally{setBusy(false);}
  }}>
    <h2 id="modal-title">{actionLabel[action]} · {account.register_label}</h2>
    <p className="payment-guidance">Held: {formatCurrency(account.held)}. Review actual authority and evidence before confirmation. This records the decision; it does not initiate an external payment.</p>
    <div className="estate-form-grid">
      {action==='requirement'?<>
        <label htmlFor="security-timing">Deposit timing<select id="security-timing" className="inp" value={form.timing} onChange={event => set('timing')(event.target.value)}>
          {!account.timing && account.required_amount != null && <option value="">Keep previously recorded terms</option>}
          {Object.entries(timingLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></label>
        {form.timing === 'before' && <>
          {input('offer_date','Offer of allotment date (optional)',{type:'date',max:form.pre_order_due_date || account.allotment_order_date})}
          {input('pre_order_due_date','Deadline from the offer (optional)',{type:'date',min:form.offer_date || undefined,max:account.allotment_order_date})}
          <p className="payment-guidance estate-wide">If the offer deadline is blank, BillTrack uses the allotment order date as the cutoff.</p>
        </>}
        {form.timing === 'after' && <p className="payment-guidance estate-wide">The deposit is due seven days after the allotment order date.</p>}
        {input('initial_monthly_rent','Reviewed initial monthly rent (₹)',{id:'security-initial-rent',type:'number',min:'0.01',step:'0.01',required:true})}
        {input('required_amount','Approved required deposit (₹; empty proposes three rents rounded up to ₹100)',{type:'number',min:'0.01',step:'0.01'})}
        {input('extended_due_date','Approved extended deposit deadline (optional)',{type:'date',max:form.timing === 'before' ? account.allotment_order_date : undefined})}
        {input('extension_reference','Deadline extension approval reference',{maxLength:250,required:Boolean(form.extended_due_date)})}
      </>:<>
        {input('amount','Total amount in this operation (₹)',{type:'number',min:'0.01',step:'0.01',required:true})}
        {input('effective_date','Actual effective date',{type:'date',max:today(),required:true})}
        {['apply_bill','apply_charge'].includes(action)&&<label htmlFor="security-target">Target obligation<select id="security-target" className="inp" required value={form[action==='apply_bill'?'bill':'charge']} onChange={event=>set(action==='apply_bill'?'bill':'charge')(event.target.value)}>
          <option value="">Choose within this award and renewal chain</option>{targets.map(target=><option key={target.id} value={target.id}>{target.register_label || target.tenant_display_name} · {target.invoice_no||target.authority_reference} · Principal {formatCurrency(target.balance_due)}{action==='apply_bill'?` · Interest ${formatCurrency(target.penalty||0)}`:''}</option>)}</select></label>}
        {action==='apply_bill'&&input('interest_amount','Interest component included in total (₹)',{type:'number',min:'0',step:'0.01',required:true})}
        {action==='refund'&&input('exception_reference','Explicit authorized exception reference (if clearance is incomplete)',{maxLength:250})}
      </>}
      {input('reference','Approval / actual payment reference',{id:'security-decision-reference',maxLength:250,required:true})}
      {input('reason','Reason and reviewed evidence',{id:'security-decision-reason',maxLength:2000,required:true})}
    </div>
    {action==='refund'&&account.clearance_issues?.length>0&&<div className="payment-guidance"><strong>Current clearance matters</strong><ul>{account.clearance_issues.map((issue,index)=><li key={index}>{issue}</li>)}</ul></div>}
    {obligations.loading&&<p role="status">Loading eligible obligations…</p>}{obligations.error&&<div role="alert">{obligations.error}<button type="button" className="btn-ghost" onClick={()=>setRetry(n=>n+1)}>Retry eligible obligations</button></div>}
    {error&&<p role="alert">{error}</p>}
    {preview?.signature===signature&&<div className="card" role="status"><p>Required deposit: {preview.before.required_amount===null?'Not reviewed':formatCurrency(preview.before.required_amount)} → {preview.after.required_amount===null?'Not reviewed':formatCurrency(preview.after.required_amount)}</p><p>Held: {formatCurrency(preview.before.held)} → {formatCurrency(preview.after.held)}</p><p>Deposit due: {formatDate(preview.after.effective_due_date)} · Refund review: {preview.after.refund_review_status}</p>
      {action==='requirement'&&preview.after.timing&&<p>Deposit timing: {timingLabel[preview.after.timing]}</p>}
      {preview.settlement&&<p>{preview.settlement.register_label} · {preview.settlement.label}: apply principal {formatCurrency(preview.settlement.principal_applied)}, interest {formatCurrency(preview.settlement.interest_applied)}; principal remaining {formatCurrency(preview.settlement.principal_remaining)}.</p>}
      {preview.clearance_issues?.length>0&&<p>Authorized exception required for {preview.clearance_issues.length} unresolved clearance matters.</p>}
      <button type="button" className="btn-primary" onClick={()=>onSave({confirmation:preview.confirmation})}>Confirm reviewed security decision</button></div>}
    <div className="estate-form-actions"><button type="button" className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" type="submit" disabled={busy||obligations.loading||Boolean(obligations.error)}>{busy?'Reviewing…':'Preview security decision'}</button></div>
  </form>;
}

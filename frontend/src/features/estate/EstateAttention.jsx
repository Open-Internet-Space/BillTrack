import { useEffect, useState } from 'react';
import API from '../../api';
import Pagination, { usePagination } from '../../Pagination';
import { formatDate } from '../../shared/format';

export const attentionLabel = {
  ending: 'Allotment ending', expired_unvacated: 'Expired — handover pending',
  handover_unknown: 'Expired — possession not confirmed', requirement: 'Document or compliance action',
  availability_unknown: 'Confirm shop availability',
  revision_due: 'Review accepted rate / April revision',
  charge_due: 'One-off charge overdue',
  vacation_overdue: 'Vacation deadline passed', bill_due: 'Bill balance overdue',
  renewal_review: 'Review extension and fee', legacy_review: 'Review historical bill assignment',
  deposit_due: 'Security deposit overdue', refund_review: 'Security refund review overdue',
  security_review: 'Record reviewed security requirement',
};

export function EstateAttention({ onOpen, onOpenBills, refreshKey }) {
  const [state, setState] = useState({ loading: true, error: '', rows: [] });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setState(old => ({ ...old, loading: true, error: '' }));
    API.getAll('/estate/attention/').then(rows => {
      if (active) setState({ loading: false, error: '', rows });
    }).catch(error => {
      if (active) setState(old => ({ ...old, loading: false, error: error.message }));
    });
    return () => { active = false; };
  }, [refreshKey, retry]);
  const pagination = usePagination(state.rows);
  return <section className="card estate-attention" aria-label="Estate attention">
    <div className="section-heading"><strong>Allotment and estate attention</strong>
      <span>{state.rows[0]?.as_of ? `As of ${formatDate(state.rows[0].as_of)} · ` : ''}Expiry window: 90 days</span></div>
    {state.loading ? <p role="status" className="estate-inset">Loading estate actions…</p>
      : state.error ? <div role="alert" className="estate-inset"><p>{state.error}</p><button className="btn-ghost" onClick={() => setRetry(n => n + 1)}>Retry estate actions</button></div>
      : <><div className="estate-attention-list" tabIndex={0} role="region" aria-label="Estate actions">
        {pagination.pageRows.length ? pagination.pageRows.map((row, index) => <button
          className="dashboard-entry estate-attention-entry" key={`${row.kind}-${row.allotment || row.shop}-${row.requirement || index}`}
          aria-label={row.bill ? `Open bill ${row.bill} for ${row.tenant_name}` : row.allotment ? `Open allotment ${row.allotment} for ${row.shop_code}` : `Open shop ${row.shop_code}`}
          onClick={() => row.bill ? onOpenBills({tenant:row.tenant,billId:row.bill,allotment:row.allotment}) : onOpen({ allotment: row.allotment, shop: row.shop, ...(row.charge ? {charge:row.charge} : {}) })}>
          <span><strong>{row.shop_code}</strong>{row.tenant_name ? ` — ${row.tenant_name}` : ''}<small>{attentionLabel[row.kind] || row.kind}{row.requirement_kind ? ` · ${row.requirement_kind}` : ''}</small></span>
          <span>{formatDate(row.due_date || row.end_date)}{row.renewal_approved && <small>Renewal approved</small>}</span>
        </button>) : <p className="estate-inset">No estate actions are currently listed.</p>}
      </div><div className="estate-pagination"><Pagination pagination={pagination} label="estate actions" /></div></>}
  </section>;
}

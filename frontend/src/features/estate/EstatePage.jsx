import { useEffect, useState } from 'react';
import API from '../../api';
import FilterBar, { matchesSearch } from '../../Filters';
import Pagination, { usePagination } from '../../Pagination';
import RefreshButton from '../../RefreshButton';
import { formatCurrency, formatDate } from '../../shared/format';
import { EstateCharges } from './EstateCharges';
import { EstateSecurity } from './EstateSecurity';

const physicalLabel = { occupied: 'Occupied', vacant: 'Vacant', unknown: 'Availability unknown' };
const termLabel = { current: 'Current', future: 'Future', expired: 'Expired', terminated: 'Terminated' };
const State = ({ value, children }) => <span className="estate-state" data-state={value}>{children || value}</span>;

export function EstatePage({ mode, context, revision, setModal, onOpenBills, user }) {
  const [state, setState] = useState({ loading: true, error: '', shops: [], terms: [], requirements: [], rates: [] });
  const [retry, setRetry] = useState(0);
  const [filters, setFilters] = useState({ search: '', status: 'all', active: 'all' });
  const [selection, setSelection] = useState(context || {});
  useEffect(() => { setSelection(context || {}); }, [context]);
  useEffect(() => {
    let active = true;
    setState(old => ({ ...old, loading: true, error: '' }));
    Promise.all([API.getAll('/shops/'), API.getAll('/allotments/'), API.getAll('/allotment-requirements/'), API.getAll('/rent-revisions/')])
      .then(([shops, terms, requirements, rates]) => { if (active) setState({ loading: false, error: '', shops, terms, requirements, rates }); })
      .catch(error => { if (active) setState(old => ({ ...old, loading: false, error: error.message })); });
    return () => { active = false; };
  }, [revision, retry]);
  const isShops = mode === 'shops';
  const rows = (isShops ? state.shops : state.terms).filter(row =>
    (matchesSearch(filters.search, row.code, row.name, row.location, row.shop_code, row.tenant_name, row.award_reference)
      || (isShops && state.terms.some(t=>t.shop===row.id && matchesSearch(filters.search,t.tenant_name,t.award_reference))))
      && (filters.status === 'all' || (isShops ? row.occupancy_status : row.status) === filters.status)
      && (!isShops || filters.active === 'all' || row.active === (filters.active === 'active'))
      && (isShops || !selection.tenant || row.tenant === selection.tenant));
  const pagination = usePagination(rows, filters);
  const selectedTerm = state.terms.find(term => term.id === selection.allotment);
  const selectedShop = state.shops.find(shop => shop.id === (selectedTerm?.shop || selection.shop));
  const shopTerms = state.terms.filter(term => term.shop === selectedShop?.id);
  const requirements = state.requirements.filter(item => item.allotment === selectedTerm?.id);
  const originalAward = selectedTerm?.original_award_id || selectedTerm?.id;
  const rates = state.rates.filter(item=>item.original_award === originalAward).sort((a,b)=>a.effective_date.localeCompare(b.effective_date));
  return <div>
    <div className="page-toolbar estate-toolbar"><h1 className="page-title">{isShops ? 'Shops' : 'Allotments'}</h1>
      <div className="toolbar-actions"><RefreshButton onRefresh={() => setRetry(n => n + 1)} busy={state.loading} />
        <button className="btn-primary" onClick={() => setModal({ type: isShops ? 'estateShop' : 'estateTerm', shops: state.shops })}>
          {isShops ? 'Add shop' : 'Record allotment'}</button></div></div>
    <p className="payment-guidance">{isShops ? 'Find a shop and review its allotment and physical handover history.'
      : 'Keep each approved term and renewal in history. Contract expiry does not confirm that a shop is vacant.'}</p>
    {state.loading ? <p role="status" className="card">Loading estate records…</p> : state.error
      ? <div role="alert" className="card"><p>{state.error}</p><button className="btn-ghost" onClick={() => setRetry(n => n + 1)}>Retry estate records</button></div>
      : <>
        {selection.tenant && <div className="bill-context"><span>Allotments for {selection.tenantName || 'selected allottee'}</span><button className="btn-ghost" onClick={() => setSelection({})}>Show all allotments</button></div>}
        <FilterBar label="Estate filters" onReset={() => setFilters({ search: '', status: 'all', active: 'all' })}>
          <label htmlFor="estate-search">Search shop / location / allottee<input id="estate-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(old => ({ ...old, search: e.target.value }))} /></label>
          <label htmlFor="estate-state">{isShops ? 'Physical availability' : 'Contract status'}<select id="estate-state" className="inp" value={filters.status} onChange={e => setFilters(old => ({ ...old, status: e.target.value }))}>
            <option value="all">All states</option>{Object.entries(isShops ? physicalLabel : termLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          {isShops && <label htmlFor="estate-active">Shop status<select id="estate-active" className="inp" value={filters.active} onChange={e => setFilters(old => ({ ...old, active: e.target.value }))}><option value="all">Active and retired</option><option value="active">Active</option><option value="retired">Retired</option></select></label>}
        </FilterBar>
        <Pagination pagination={pagination} label={isShops ? 'shops' : 'allotments'} />
        <div className="card table-scroll estate-table" role="region" aria-label="Estate records" tabIndex={0}>
          <table><thead><tr>{(isShops ? ['Shop', 'Location / activity', 'Type', 'Physical availability', 'Current term / dues', 'Actions']
            : ['Shop / allottee', 'Award reference', 'Contract dates', 'Contract status', 'Term dues', 'Actions']).map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>
            {pagination.pageRows.map(row => <tr key={row.id} className="row-hover">
              {isShops ? <><td><strong>{row.code}</strong><small>{row.name}</small></td><td>{row.location || 'Not recorded'}<small>{row.authorized_services}</small></td>
                <td>{row.space_type === 'room' ? 'Constructed room' : 'Space'}<small>{row.active ? 'Active' : 'Retired'}</small></td>
                <td><State value={row.occupancy_status}>{physicalLabel[row.occupancy_status]}</State></td>
                <td>{state.terms.filter(t=>t.shop===row.id && t.status==='current').map(t=><div key={t.id}>{t.tenant_name}
                  <small>Through {formatDate(t.effective_end)} · {formatCurrency(t.total_due)} due</small></div>)}
                  {!state.terms.some(t=>t.shop===row.id && t.status==='current') && 'No current term'}</td></>
                : <><td><strong>{row.shop_code}</strong><small>{row.tenant_name}</small></td><td>{row.award_reference}</td>
                  <td>{formatDate(row.start_date)} — {formatDate(row.effective_end || row.end_date)}</td>
                  <td><State value={row.status}>{termLabel[row.status]}</State><small>{row.extension_number ? `Extension ${row.extension_number}` : 'Original award'}</small></td><td>{formatCurrency(row.total_due)}</td></>}
              <td><div className="estate-actions"><button className="btn-ghost" onClick={() => setSelection(isShops ? { shop: row.id } : { allotment: row.id })}>{isShops ? 'History' : 'Details'}</button>
                <button className="btn-ghost" onClick={() => setModal({ type: isShops ? 'estateShop' : 'estateTerm', data: row, shops: state.shops })}>Edit</button></div></td>
            </tr>)}
            {!rows.length && <tr><td colSpan={5}>{filters.search || filters.status !== 'all' ? 'No records match these filters.' : `No ${isShops ? 'shops' : 'allotments'} recorded yet.`}</td></tr>}
          </tbody></table>
        </div>
        {selectedShop && <section className="estate-detail" aria-label="Shop history">
          <div className="estate-toolbar"><h2>{selectedShop.code} — {selectedShop.name}</h2>
            <button className="btn-primary" disabled={!selectedShop.active} onClick={() => setModal({ type: 'estateTerm', shops: state.shops, shop: selectedShop.id })}>Record allotment for this shop</button></div>
          <p>Physical availability: <State value={selectedShop.occupancy_status}>{physicalLabel[selectedShop.occupancy_status]}</State></p>
          <p>Initial availability evidence: {selectedShop.availability_reference || 'Not recorded'} · {formatDate(selectedShop.availability_confirmed_on)}</p>
          <ul className="estate-history">{shopTerms.map(term => <li key={term.id}><button className="btn-ghost" onClick={() => setSelection({ allotment: term.id })}>{term.tenant_name} · {term.award_reference} · {formatDate(term.start_date)} — {formatDate(term.end_date)}</button><State value={term.status}>{termLabel[term.status]}</State></li>)}</ul>
          {!shopTerms.length && <p>No allotment history recorded.</p>}
        </section>}
        {selectedTerm && <section className="estate-detail" aria-label="Allotment details">
          <div className="estate-toolbar"><h2>{selectedTerm.shop_code} · {selectedTerm.award_reference}</h2>
            <div className="estate-actions"><button className="btn-ghost" onClick={() => setModal({ type: 'estateTerm', data: selectedTerm, shops: state.shops })}>Edit term / handover</button>
              <button className="btn-ghost" onClick={() => onOpenBills({ tenant: selectedTerm.tenant, allotment: selectedTerm.id, shopCode: selectedTerm.shop_code })}>View term bills</button>
              <button className="btn-ghost" onClick={() => setModal({ type: 'addBill', tenant: selectedTerm.tenant, allotment: selectedTerm.id })}>Raise bill for term</button>
              <button className="btn-primary" disabled={selectedTerm.renewal_fee_settled===false || selectedTerm.extension_number >= 2 || state.terms.some(term => term.renewal_of === selectedTerm.id)} onClick={() => setModal({ type: 'estateTerm', renewalOf: selectedTerm, shops: state.shops })}>Record renewal</button></div></div>
          <dl className="estate-facts">
            <div><dt>Allottee</dt><dd>{selectedTerm.tenant_name}</dd></div><div><dt>Source notice</dt><dd>{selectedTerm.source_notice}</dd></div>
            <div><dt>Contract dates</dt><dd>{formatDate(selectedTerm.start_date)} — {formatDate(selectedTerm.end_date)}</dd></div>
            <div><dt>Actual allotted area</dt><dd>{selectedTerm.actual_area} sq ft · {selectedTerm.measurement_reference}</dd></div>
            <div><dt>Possession</dt><dd>{formatDate(selectedTerm.possession_date)} · {selectedTerm.possession_reference || 'Not recorded'}</dd></div>
            <div><dt>Physical handover</dt><dd>{formatDate(selectedTerm.handover_date)} · {selectedTerm.handover_reference || 'Not recorded'}</dd></div>
            <div><dt>Approval / performance</dt><dd>{selectedTerm.approval_reference || 'Not recorded'} · {selectedTerm.performance_reference || 'Not recorded'}</dd></div>
          </dl>
          <div className="estate-toolbar"><h3>Approved rent schedule</h3><button className="btn-ghost" onClick={()=>setModal({type:'estateRate',originalAward,previousRate:rates[rates.length-1]})}>{rates.length ? 'Record annual revision' : 'Record accepted rate'}</button></div>
          {rates.length ? <ul className="estate-history">{rates.map(rate=><li key={rate.id}><span>{formatDate(rate.effective_date)} · ₹{rate.rate}/sq ft · {rate.approval_reference}</span><button className="btn-ghost" onClick={()=>setModal({type:'estateRate',originalAward,data:rate})}>Correct rate evidence</button></li>)}</ul> : <p>No accepted rate recorded. Final notice billing requires reviewed rate evidence.</p>}
          <EstateCharges term={selectedTerm} revision={revision} setModal={setModal} user={user} initialCharge={selection.charge} />
          <EstateSecurity originalAward={originalAward} chain={state.terms.filter(term=>(term.original_award_id||term.id)===originalAward)} revision={revision} setModal={setModal} user={user} />
          <h3>Documents and conditions</h3>
          {requirements.length ? <ul className="estate-history">{requirements.map(item => <li key={item.id}>
            <span>{item.kind} · {item.status} · Due {formatDate(item.due_date)}</span>
            <button className="btn-ghost" onClick={() => setModal({ type: 'estateRequirement', data: item })}>Update evidence</button></li>)}</ul> : <p>No conditions recorded on this term. Review the original award for renewal evidence.</p>}
        </section>}
      </>}
  </div>;
}

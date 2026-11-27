import { useEffect, useState } from 'react';
import API from '../../api';
import FilterBar, { matchesSearch } from '../../Filters';
import Pagination, { usePagination } from '../../Pagination';
import RefreshButton from '../../RefreshButton';
import { formatCurrency, formatDate } from '../../shared/format';
import { EstateCharges } from './EstateCharges';
import { EstateSecurity } from './EstateSecurity';

const termLabel = { current: 'Current', future: 'Future', expired: 'Expired', terminated: 'Terminated' };
const State = ({ value, children }) => <span className="estate-state" data-state={value}>{children || value}</span>;

function RentSchedule({ term, rates, setModal }) {
  const options = { type: 'estateRate', originalAward: term.original_award_id || term.id,
    flat: term.rent_basis === 'flat', notice: term.notice_governed };
  return <section aria-label="Rent schedule">
    <div className="estate-toolbar"><h3>Rent schedule</h3>
      <button className="btn-ghost" onClick={() => setModal({ ...options, previousRate: rates.at(-1) })}>
        {rates.length ? 'Add rent revision' : 'Record accepted rate'}</button>
    </div>
    {rates.length ? <ul className="estate-history">{rates.map(rate => <li key={rate.id}>
      <span>{formatDate(rate.effective_date)} · ₹{rate.rate}{options.flat ? ' per month' : ' per sq ft'}
        {rate.approval_reference && ` · ${rate.approval_reference}`}</span>
      <button className="btn-ghost" onClick={() => setModal({ ...options, data: rate })}>Correct rate evidence</button>
    </li>)}</ul> : <p>No rent rate recorded.</p>}
  </section>;
}

export function EstatePage({ context, revision, setModal, onOpenBills, onBack, user, tenantActive, showToast, onDeleteTerm, onDeleteCharge, deleting }) {
  const [state, setState] = useState({ loading: true, error: '', terms: [], requirements: [], rates: [] });
  const [retry, setRetry] = useState(0);
  const [filters, setFilters] = useState({ search: '', status: 'all' });
  const [selection, setSelection] = useState(context || {});
  const rateTenant = context?.rentRates ? context.tenant : null;
  useEffect(() => { setSelection(context || {}); }, [context]);
  useEffect(() => {
    let active = true;
    setState(old => ({ ...old, loading: true, error: '' }));
    Promise.all(rateTenant ? [API.getAll(`/allotments/?tenant=${rateTenant}`), [], API.getAll(`/rent-revisions/?original_award__tenant=${rateTenant}`)]
      : [API.getAll('/allotments/'), API.getAll('/allotment-requirements/'), API.getAll('/rent-revisions/')])
      .then(([terms, requirements, rates]) => { if (active) setState({ loading: false, error: '', terms, requirements, rates }); })
      .catch(error => { if (active) setState(old => ({ ...old, loading: false, error: error.message })); });
    return () => { active = false; };
  }, [revision, retry, rateTenant]);
  const rows = state.terms.filter(row =>
    matchesSearch(filters.search, row.register_label || row.tenant_name, row.award_reference)
      && (filters.status === 'all' || row.status === filters.status)
      && (!context?.tenant || row.tenant === context.tenant));
  const pagination = usePagination(rows, filters);
  const awards = rateTenant ? state.terms.filter(term => term.tenant === rateTenant && !term.renewal_of) : [];
  const selectedTerm = rateTenant ? awards.find(term => term.id === selection.allotment) || (awards.length === 1 ? awards[0] : null)
    : state.terms.find(term => term.id === selection.allotment);
  const requirements = state.requirements.filter(item => item.allotment === selectedTerm?.id);
  const originalAward = selectedTerm?.original_award_id || selectedTerm?.id;
  const renewedTerms = new Set(state.terms.map(term => term.renewal_of));
  const predecessors = term => term.renewal_of || renewedTerms.has(term.id) ? [] : state.terms.filter(other =>
    other.tenant === term.tenant && other.shop === term.shop && (other.effective_end || other.end_date) < term.start_date &&
    other.extension_number < 2 && other.notice_governed === term.notice_governed && other.rent_basis === term.rent_basis && !renewedTerms.has(other.id));
  const rates = state.rates.filter(item=>item.original_award === originalAward).sort((a,b)=>a.effective_date.localeCompare(b.effective_date));
  return <div>
    <div className="page-toolbar estate-toolbar"><h1 className="page-title">{rateTenant ? 'Rent rates' : 'Allotments'}</h1>
      <div className="toolbar-actions">
        <button className="btn-ghost" onClick={onBack}>Back to allotments</button>
        <RefreshButton onRefresh={() => setRetry(n => n + 1)} busy={state.loading} />
        <button className="btn-primary" disabled={state.loading || Boolean(state.error) || tenantActive === false}
          onClick={() => setModal({ type: 'estateTerm', tenant: context?.tenant })}>
          Record term</button></div></div>
    <h2>{rateTenant ? context.tenantName : context?.tenantName ? `Terms for ${context.tenantName}` : 'Contract terms'}</h2>
    {state.loading ? <p role="status" className="card">Loading estate records…</p> : state.error
      ? <div role="alert" className="card"><p>{state.error}</p><button className="btn-ghost" onClick={() => setRetry(n => n + 1)}>Retry estate records</button></div>
      : rateTenant ? <>
        {!awards.length && <p>Record an allotment term to start its rent schedule.</p>}
        {awards.length > 1 && <label htmlFor="rent-schedule-award">Allotment award
          <select id="rent-schedule-award" className="inp" value={selectedTerm?.id || ''}
            onChange={event => setSelection({ allotment: Number(event.target.value) })}>
            <option value="">Choose an award</option>
            {awards.map(term => <option key={term.id} value={term.id}>{term.award_reference} · {formatDate(term.start_date)}</option>)}
          </select>
        </label>}
        {selectedTerm && <RentSchedule term={selectedTerm} rates={rates} setModal={setModal} />}
      </> : <>
        <FilterBar label="Estate filters" onReset={() => setFilters({ search: '', status: 'all' })}>
          <label htmlFor="estate-search">Search allotment or award reference<input id="estate-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(old => ({ ...old, search: e.target.value }))} /></label>
          <label htmlFor="estate-state">Contract status<select id="estate-state" className="inp" value={filters.status} onChange={e => setFilters(old => ({ ...old, status: e.target.value }))}>
            <option value="all">All states</option>{Object.entries(termLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </FilterBar>
        <Pagination pagination={pagination} label="terms" />
        <div className="card table-scroll estate-table" role="region" aria-label="Estate records" tabIndex={0}>
          <table><thead><tr>{['Allotment', 'Award reference', 'Contract dates', 'Contract status', 'Term dues', 'Actions']
            .map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>
            {pagination.pageRows.map(row => <tr key={row.id} className="row-hover">
              <td>{row.register_label || row.tenant_name}</td><td>{row.award_reference}</td>
              <td>{formatDate(row.start_date)} — {formatDate(row.effective_end || row.end_date)}</td>
              <td><State value={row.status}>{termLabel[row.status]}</State><small>{row.extension_number ? `Extension ${row.extension_number}` : 'Original award'}</small></td>
              <td>{formatCurrency(row.total_due)}</td>
              <td><div className="estate-actions">
                <button className="btn-ghost" onClick={() => setSelection({ allotment: row.id })}>Details</button>
                <button className="btn-ghost" onClick={() => setModal({ type: 'estateTerm', data: row })}>Edit</button>
                {user?.is_superuser && predecessors(row).length > 0 && <button className="btn-ghost"
                  onClick={() => setModal({ type: 'linkExtension', term: row, candidates: predecessors(row) })}>Link as extension</button>}
                <button type="button" className="btn-ghost" disabled={deleting} aria-label={`Delete term ${row.award_reference}`}
                  onClick={() => onDeleteTerm(row.id)}>Delete</button>
              </div></td>
            </tr>)}
            {!rows.length && <tr><td colSpan={6}>{filters.search || filters.status !== 'all' ? 'No records match these filters.' : 'No terms recorded yet.'}</td></tr>}
          </tbody></table>
        </div>
        {selectedTerm && <section className="estate-detail" aria-label="Allotment details">
          <div className="estate-toolbar"><h2>{selectedTerm.register_label || selectedTerm.tenant_name} · {selectedTerm.award_reference}</h2>
            <div className="estate-actions"><button className="btn-ghost" onClick={() => setModal({ type: 'estateTerm', data: selectedTerm })}>{user?.allotment_details_enabled ? 'Edit term / handover' : 'Edit term'}</button>
              <button className="btn-ghost" onClick={() => onOpenBills({ tenant: selectedTerm.tenant, allotment: selectedTerm.id, registerLabel: selectedTerm.register_label || selectedTerm.tenant_name })}>View term bills</button>
              <button className="btn-ghost" onClick={() => setModal({ type: 'addBill', tenant: selectedTerm.tenant, allotment: selectedTerm.id })}>Raise bill for term</button>
              <button className="btn-primary" disabled={selectedTerm.renewal_fee_settled===false || selectedTerm.extension_number >= 2 || state.terms.some(term => term.renewal_of === selectedTerm.id)} onClick={() => setModal({ type: 'estateTerm', renewalOf: selectedTerm })}>Record renewal</button></div></div>
          <dl className="estate-facts">
            {selectedTerm.premises_label && <div><dt>Premises</dt><dd>{selectedTerm.premises_label}</dd></div>}
            <div><dt>Allottee</dt><dd>{selectedTerm.tenant_name}</dd></div><div><dt>Source notice</dt><dd>{selectedTerm.source_notice || '—'}</dd></div>
            <div><dt>Contract dates</dt><dd>{formatDate(selectedTerm.start_date)} — {formatDate(selectedTerm.end_date)}</dd></div>
            {selectedTerm.exception_reference && <div><dt>Approved date exception</dt><dd>{selectedTerm.exception_reference}
              {selectedTerm.exception_reason && <><br />{selectedTerm.exception_reason}</>}</dd></div>}
            {selectedTerm.rent_basis === 'flat' ? <div><dt>Monthly charge basis</dt><dd>Flat monthly charge</dd></div>
              : <div><dt>Actual allotted area</dt><dd>{selectedTerm.actual_area} sq ft · {selectedTerm.measurement_reference}</dd></div>}
            {user?.allotment_details_enabled && <>
              <div><dt>Possession</dt><dd>{formatDate(selectedTerm.possession_date)} · {selectedTerm.possession_reference || 'Not recorded'}</dd></div>
              <div><dt>Physical handover</dt><dd>{formatDate(selectedTerm.handover_date)} · {selectedTerm.handover_reference || 'Not recorded'}</dd></div>
            </>}
            <div><dt>Approval / performance</dt><dd>{selectedTerm.approval_reference || 'Not recorded'} · {selectedTerm.performance_reference || 'Not recorded'}</dd></div>
          </dl>
          <RentSchedule term={selectedTerm} rates={rates} setModal={setModal} />
          <EstateCharges term={selectedTerm} revision={revision} setModal={setModal} user={user} initialCharge={selection.charge}
            showToast={showToast} onDelete={onDeleteCharge} deleting={deleting} />
          <EstateSecurity originalAward={originalAward} term={selectedTerm} chain={state.terms.filter(term=>(term.original_award_id||term.id)===originalAward)} revision={revision} setModal={setModal} user={user} />
          <h3>Documents and conditions</h3>
          {requirements.length ? <ul className="estate-history">{requirements.map(item => <li key={item.id}>
            <span>{item.kind} · {item.status} · Due {formatDate(item.due_date)}</span>
            <button className="btn-ghost" onClick={() => setModal({ type: 'estateRequirement', data: item })}>Update evidence</button></li>)}</ul> : <p>No conditions recorded on this term. Review the original award for renewal evidence.</p>}
        </section>}
      </>}
  </div>;
}

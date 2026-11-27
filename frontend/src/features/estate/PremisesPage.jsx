import { useEffect, useState } from 'react';
import API from '../../api';
import FilterBar, { matchesSearch } from '../../Filters';
import Pagination, { usePagination } from '../../Pagination';
import RefreshButton from '../../RefreshButton';

const availability = { occupied: 'Occupied', vacant: 'Vacant', unknown: 'Availability unknown' };

export function PremisesPage({ revision, onBack, onDelete, deleting, setModal, selectedId }) {
  const [state, setState] = useState({ rows: [], loading: true, error: '' });
  const [retry, setRetry] = useState(0);
  const [filters, setFilters] = useState({ search: '', status: '', active: '' });
  useEffect(() => {
    let active = true;
    setState(previous => ({ ...previous, loading: true, error: '' }));
    API.getAll('/shops/').then(rows => {
      if (active) setState({ rows, loading: false, error: '' });
    }).catch(error => {
      if (active) setState({ rows: [], loading: false, error: error.message });
    });
    return () => { active = false; };
  }, [revision, retry]);
  const rows = state.rows.filter(row => matchesSearch(filters.search, row.code, row.name, row.location, row.authorized_services)
    && (!filters.status || row.occupancy_status === filters.status)
    && (!filters.active || row.active === (filters.active === 'active'))
    && (!selectedId || row.id === selectedId));
  const pagination = usePagination(rows, filters);
  const filter = key => event => setFilters(previous => ({ ...previous, [key]: event.target.value }));

  return <div>
    <div className="page-toolbar estate-toolbar"><h1 className="page-title">Premises</h1>
      <div className="toolbar-actions">
        <button className="btn-ghost" onClick={onBack}>Back to allotments</button>
        <RefreshButton onRefresh={() => setRetry(value => value + 1)} busy={state.loading} />
        <button className="btn-primary" onClick={() => setModal({ type: 'estateShop' })}>Add premises</button>
      </div>
    </div>
    {state.loading ? <p role="status" className="card">Loading premises…</p> : state.error
      ? <div role="alert" className="card"><p>{state.error}</p><button className="btn-ghost" onClick={() => setRetry(value => value + 1)}>Retry</button></div>
      : <>
        <FilterBar label="Premises filters" onReset={() => setFilters({ search: '', status: '', active: '' })}>
          <label>Search code, name or location<input type="search" className="inp" value={filters.search} onChange={filter('search')} /></label>
          <label>Physical availability<select className="inp" value={filters.status} onChange={filter('status')}>
            <option value="">All states</option>{Object.entries(availability).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
          <label>Record status<select className="inp" value={filters.active} onChange={filter('active')}>
            <option value="">Active and retired</option><option value="active">Active</option><option value="retired">Retired</option>
          </select></label>
        </FilterBar>
        <Pagination pagination={pagination} label="premises" />
        <div className="card table-scroll estate-table" role="region" aria-label="Premises records" tabIndex={0}>
          <table><thead><tr><th>Premises</th><th>Location</th><th>Physical availability</th><th>Actions</th></tr></thead>
            <tbody>{pagination.pageRows.map(row => <tr key={row.id} className="row-hover">
              <td><strong>{row.code}</strong><small>{row.name}</small></td><td>{row.location || '—'}</td>
              <td><span className="estate-state" data-state={row.occupancy_status}>{availability[row.occupancy_status]}</span>
                {!row.active && <small>Retired</small>}</td>
              <td><div className="estate-actions">
                <button className="btn-ghost" onClick={() => setModal({ type: 'estateShop', data: row })}>Edit</button>
                <button className="btn-ghost" disabled={deleting} aria-label={`Delete premises ${row.code}`} onClick={() => onDelete(row.id)}>Delete</button>
              </div></td>
            </tr>)}
            {!rows.length && <tr><td colSpan={4}>No premises found.</td></tr>}</tbody>
          </table>
        </div>
      </>}
  </div>;
}

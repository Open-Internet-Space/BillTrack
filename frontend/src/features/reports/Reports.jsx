import { useState } from 'react';
import Pagination, { usePagination } from '../../Pagination';
import RefreshButton from '../../RefreshButton';

const REPORTS = {
  pending: 'Pending bills', payments: 'Payments received', penalties: 'Penalties',
  bills: 'Bills register', statement: 'Bills and payments statement',
};
const money = value => Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const localToday = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
};

export default function Reports({ api, tenants, refresh }) {
  const [filters, setFilters] = useState(() => ({ report: 'pending', from: `${localToday().slice(0, 7)}-01`,
    to: localToday(), tenant: '', type: '', status: '', receipt_status: '', billing_from: '', billing_to: '' }));
  const [report, setReport] = useState(null);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState('');
  const [error, setError] = useState('');
  const pagination = usePagination(report?.rows || [], report);
  const visibleColumns = report?.columns.filter(column => selectedColumns.includes(column.key)) || [];
  const periodReport = ['payments', 'bills', 'statement'].includes(filters.report);
  const change = event => {
    setFilters(current => ({ ...current, ...(event.target.name === 'report' ? { billing_from: '', billing_to: '' } : {}), [event.target.name]: event.target.value }));
    setReport(null);
    setError('');
  };
  const preview = async (event, keepColumns = false) => {
    event.preventDefault();
    if (loading || downloading) return;
    setLoading(true);
    setReport(null);
    setError('');
    const params = new URLSearchParams(Object.entries(filters).filter(([key, value]) => value && (key !== 'from' || periodReport)));
    try {
      const data = await api.get(`/reports/?${params}`);
      const columns = data.columns.map(column => column.key);
      setSelectedColumns(keepColumns && report ? columns.filter(key => selectedColumns.includes(key)) : columns);
      setReport(data);
    }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };
  const download = async output => {
    if (!report || downloading || !selectedColumns.length) return;
    setDownloading(output);
    setError('');
    try { await api.download('/reports/', { snapshot: report.snapshot, output, columns: selectedColumns }, `${filters.report}-report-${filters.to}.${output}`); }
    catch (err) { setError(err.message); }
    finally { setDownloading(''); }
  };
  return <section className="reports-page" aria-labelledby="reports-title">
    <div className="page-toolbar" style={{ display: 'flex', justifyContent: 'space-between' }}>
      <h1 id="reports-title" className="page-title">Reports</h1>
      <RefreshButton busy={loading || Boolean(downloading)} onRefresh={event => {
        refresh?.();
        preview(event, true);
      }} />
    </div>
    <p className="report-intro">Choose a report and review the figures before downloading a copy for submission.</p>
    <form onSubmit={preview}>
      <fieldset disabled={loading || Boolean(downloading)} className="report-fieldset">
        <legend className="sr-only">Report filters</legend>
        <div className="record-filters">
          <label htmlFor="report-kind">Report
            <select id="report-kind" name="report" className="inp" value={filters.report} onChange={change}>
              {Object.entries(REPORTS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>
          <label htmlFor="report-tenant">Vendor
            <select id="report-tenant" name="tenant" className="inp" value={filters.tenant} onChange={change}>
              <option value="">All vendors</option>
              {tenants.map(tenant => <option key={tenant.id} value={tenant.id}>{tenant.name}</option>)}
            </select>
          </label>
          <label htmlFor="report-type">Vendor type
            <select id="report-type" name="type" className="inp" value={filters.type} onChange={change}>
              <option value="">All types</option>
              {['Shop', 'Canteen', 'Contractor'].map(type => <option key={type}>{type}</option>)}
            </select>
          </label>
          {periodReport && <label htmlFor="report-from">{filters.report === 'bills' ? 'From billing month' : filters.report === 'statement' ? 'From date' : 'From payment date'}
            <input id="report-from" name="from" className="inp" type={filters.report === 'bills' ? 'month' : 'date'}
              required={filters.report === 'statement'} value={filters.report === 'bills' ? filters.from.slice(0, 7) : filters.from}
              max={filters.report === 'bills' ? filters.to.slice(0, 7) : filters.to}
              onChange={event => change({ target: { name: 'from', value: event.target.value && (filters.report === 'bills' ? `${event.target.value}-01` : event.target.value) } })} />
          </label>}
          <label htmlFor="report-to">{periodReport ? 'Through / cutoff date' : 'Position as of'}
            <input id="report-to" name="to" className="inp" type="date" required max={localToday()} value={filters.to} onChange={change} />
          </label>
          <label htmlFor="report-status">Payment status at cutoff
            <select id="report-status" name="status" className="inp" value={filters.status} onChange={change}>
              <option value="">All statuses</option>
              {['Unpaid', 'Partial', 'Paid'].map(status => <option key={status}>{status}</option>)}
            </select>
          </label>
          <label htmlFor="report-receipt">Bill receipt status at cutoff
            <select id="report-receipt" name="receipt_status" className="inp" value={filters.receipt_status} onChange={change}>
              <option value="">All receipt statuses</option><option value="pending">Pending Receipt</option><option value="confirmed">Receipt Confirmed</option>
            </select>
          </label>
          {filters.report !== 'bills' && <>
            <label htmlFor="report-billing-from">From billing month (optional)
              <input id="report-billing-from" name="billing_from" className="inp" type="month" max={filters.billing_to || filters.to.slice(0, 7)} value={filters.billing_from} onChange={change} />
            </label>
            <label htmlFor="report-billing-to">To billing month (optional)
              <input id="report-billing-to" name="billing_to" className="inp" type="month" min={filters.billing_from} value={filters.billing_to} onChange={change} />
            </label>
          </>}
        </div>
        <p className="report-hint">{!periodReport ? (filters.report === 'penalties' ? 'Includes accrued and collected penalties through the cutoff, including settled bills.' : 'Includes earlier bills with outstanding principal or penalty through the cutoff.')
          : filters.report === 'bills' ? 'Selects bills by accounting month. Payment totals reflect the cutoff date.'
            : filters.report === 'statement' ? 'Opening dues and period movements reconcile to closing dues. Negative dues are credits.'
              : 'Selects receipts by payment date, including payments against older bills.'}</p>
        <button type="submit" className="btn-primary">{loading ? 'Preparing preview…' : 'Preview report'}</button>
      </fieldset>
    </form>
    {!report && <div className="report-downloads" aria-label="Report downloads">
      {['docx', 'xlsx', 'pdf'].map(output => <button key={output} className="btn-ghost" disabled>Download {output.toUpperCase()}</button>)}
      <span>Preview the report to choose columns and download.</span>
    </div>}
    {error && <p className="report-error" role="alert">{error}</p>}
    {loading && <p role="status">Calculating report…</p>}
    {!report && !loading && <p className="report-empty">Select your filters, then choose Preview report to review the figures.</p>}
    {report && <section className="report-preview" aria-label="Report preview">
      <h2>{report.title}</h2>
      <p>{report.organisation}{report.department ? ` · ${report.department}` : ''}</p>
      <p>{report.filters}</p>
      <p className="report-hint">Generated: {report.generated_at} · {report.count} records · All amounts in INR</p>
      <fieldset className="report-columns" disabled={Boolean(downloading)}>
        <legend>Download columns</legend>
        <p className="report-hint">All columns are selected by default. Uncheck any column to leave it out of the preview and downloads.</p>
        <div className="report-column-options">{report.columns.map(column => <label key={column.key}>
          <input type="checkbox" value={column.key} checked={selectedColumns.includes(column.key)} onChange={event => setSelectedColumns(current =>
            event.target.checked ? [...current, column.key] : current.filter(key => key !== column.key))} />
          {column.label}
        </label>)}</div>
        <button type="button" className="btn-ghost" onClick={() => setSelectedColumns(report.columns.map(column => column.key))}>Select all columns</button>
      </fieldset>
      {!selectedColumns.length && <p role="status" className="report-hint">Select at least one column to download.</p>}
      <div className="report-downloads" aria-label="Report downloads">
        {['docx', 'xlsx', 'pdf'].map(output => <button key={output} className="btn-ghost" disabled={!selectedColumns.length || Boolean(downloading)} onClick={() => download(output)}>
          {downloading === output ? `Preparing ${output.toUpperCase()}…` : `Download ${output.toUpperCase()}`}
        </button>)}
        <span>Downloads contain every row with the selected columns. Preview valid for one hour.</span>
      </div>
      <div className="report-table-scroll" role="region" aria-label="Report figures" tabIndex={0}>
        <table>
          <thead><tr><th scope="col">No.</th>{visibleColumns.map(column => <th scope="col" key={column.key} className={column.numeric ? 'report-money' : ''}>{column.label}</th>)}</tr></thead>
          <tbody>{pagination.pageRows.map((row, index) => <tr key={pagination.pageStart + index} className="row-hover">
            <td>{pagination.pageStart + index + 1}</td>
            {visibleColumns.map(column => <td key={column.key} className={column.numeric ? 'report-money' : ''}>
              {column.numeric ? money(row[column.key]) : row[column.key] || '—'}
            </td>)}
          </tr>)}</tbody>
          <tfoot><tr><th scope="row">Totals</th>{visibleColumns.map(column => <td key={column.key} className={column.numeric ? 'report-money' : ''}>
            {column.numeric ? money(report.totals[column.key]) : ''}
          </td>)}</tr></tfoot>
        </table>
      </div>
      {report.count === 0 && <p className="report-empty">No records match these filters. Try another period or vendor.</p>}
      <Pagination pagination={pagination} label="report rows" />
      <div className="report-notes">{report.notes.map(note => <p key={note}>{note}</p>)}</div>
    </section>}
  </section>;
}

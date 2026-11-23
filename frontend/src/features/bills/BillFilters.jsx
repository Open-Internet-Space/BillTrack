import Pagination from "../../Pagination";

export function BillFilters({ filters, billRows, setFilters, changeFilter, types, tenantOptions, yearOptions, monthOptions, pagination }) {
  return (<div className="card" style={{ padding: "12px 14px", marginBottom: 14 }}>
        {filters.allotment && <div className="bill-context"><span>Bills for {filters.shopCode || 'selected shop'} · allotment term {filters.allotment}</span><button className="btn-ghost" onClick={() => setFilters(previous => ({ ...previous, allotment: null, shopCode: '' }))}>Show all allottee bills</button></div>}
        {filters.billId && <div className="bill-context"><span>Opened from Dashboard: {billRows.find(b => b.id === filters.billId)?.invoice_no || "selected bill"}</span><button className="btn-ghost" onClick={() => setFilters(previous => ({ ...previous, billId: null }))}>Show all allottee bills</button></div>}
        <div className="filter-grid">
          <label htmlFor="bills-search">Search invoice / reference<input id="bills-search" className="inp" type="search" value={filters.search} onChange={e => changeFilter("search", e.target.value)} /></label>
          <label htmlFor="bills-type">Allottee Type<select id="bills-type" className="inp" value={filters.type} onChange={e => changeFilter("type", e.target.value)}><option value="all">All Types</option>{types.map(type => <option key={type} value={type}>{type}</option>)}</select></label>
          <div>
            <label htmlFor="bills-tenant">Allottee</label>
            <select id="bills-tenant" className="inp" value={filters.tenant} onChange={e => changeFilter("tenant", e.target.value)}>
              <option value="all">All Allottees</option>
              {tenantOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="bills-status">Status</label>
            <select id="bills-status" className="inp" value={filters.status} onChange={e => changeFilter("status", e.target.value)}>
              <option value="all">All Status</option>
              <option value="Unpaid">Unpaid</option>
              <option value="Partial">Partial</option>
              <option value="Paid">Paid</option>
            </select>
          </div>
          <div>
            <label htmlFor="bills-year">Year</label>
            <select id="bills-year" className="inp" value={filters.year} onChange={e => changeFilter("year", e.target.value)}>
              <option value="all">All Years</option>
              {yearOptions.map(year => <option key={year} value={year}>{year}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="bills-month">Month</label>
            <select id="bills-month" className="inp" value={filters.month} onChange={e => changeFilter("month", e.target.value)}>
              <option value="all">All Months</option>
              {monthOptions.map(([month, label]) => <option key={month} value={month}>{label}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="bills-receipt">Email / Receipt Status</label>
            <select id="bills-receipt" className="inp" value={filters.receipt} onChange={e => changeFilter("receipt", e.target.value)}>
              <option value="all">All confirmation states</option>
              <option value="pending">Pending email / receipt</option>
              <option value="confirmed">Confirmed email / receipt</option>
            </select>
          </div>
          <button className="btn-ghost" style={{ padding: "9px 14px", fontSize: 12 }} onClick={() => setFilters({ tenant: "all", status: "all", receipt: "all", search: "", type: "all", year: "all", month: "all" })}>
            Reset
          </button>
        </div>
        <Pagination pagination={pagination} label="bills" />
      </div>);
}

import { useState, useEffect, useMemo } from "react";
import Pagination, { usePagination } from "../../Pagination";
import { matchesSearch, withinDates } from "../../Filters";
import RefreshButton from "../../RefreshButton";
import { formatCurrency, formatDate } from "../../shared/format.js";

export function Payments({ payments, refresh, refreshing }) {
  const paymentRows = useMemo(() => Array.isArray(payments) ? payments : [], [payments]);
  const [filters, setFilters] = useState({ tenant: "all", year: "all", month: "all", search: "", from: "", to: "" });
  const tenantOptions = useMemo(() => {
    const map = new Map();
    paymentRows.forEach(p => map.set(String(p.bill_tenant), p.bill_tenant_name));
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [paymentRows]);
  const yearOptions = useMemo(() => [...new Set(paymentRows.map(p => p.bill_year))].filter(Boolean).sort((a, b) => b - a), [paymentRows]);
  const monthOptions = useMemo(() => [...new Set(paymentRows.map(p => p.bill_month))].filter(Boolean).sort((a, b) => a - b), [paymentRows]);
  const filteredRows = useMemo(() => paymentRows.filter(p =>
    matchesSearch(filters.search, p.receipt_no, p.bill_invoice, p.bill_tenant_name)
    && withinDates(p.payment_date, filters.from, filters.to) &&
    (filters.tenant === "all" || String(p.bill_tenant) === filters.tenant) &&
    (filters.year === "all" || String(p.bill_year) === filters.year) &&
    (filters.month === "all" || String(p.bill_month) === filters.month)
  ), [paymentRows, filters]);
  const pagination = usePagination(filteredRows);
  const { pageSize, setPage, pageRows } = pagination;

  useEffect(() => setPage(1), [filters, pageSize, setPage]);

  return (
    <div>
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 className="page-title">Payment Register</h1>
        <RefreshButton onRefresh={refresh} busy={refreshing} />
      </div>
      <div className="card" style={{ padding: "12px 14px", marginBottom: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, alignItems: "end" }}>
          <div><label htmlFor="payments-vendor">Allottee</label><select id="payments-vendor" className="inp" value={filters.tenant} onChange={e => setFilters(f => ({ ...f, tenant: e.target.value }))}>
            <option value="all">All Allottees</option>
            {tenantOptions.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select></div>
          <div><label htmlFor="payments-bill-year">Bill Year</label><select id="payments-bill-year" className="inp" value={filters.year} onChange={e => setFilters(f => ({ ...f, year: e.target.value }))}>
            <option value="all">All Years</option>
            {yearOptions.map(year => <option key={year} value={year}>{year}</option>)}
          </select></div>
          <div><label htmlFor="payments-bill-month">Bill Month</label><select id="payments-bill-month" className="inp" value={filters.month} onChange={e => setFilters(f => ({ ...f, month: e.target.value }))}>
            <option value="all">All Months</option>
            {monthOptions.map(month => <option key={month} value={month}>{new Date(2000, month - 1, 1).toLocaleString("en-IN", { month: "short" })}</option>)}
          </select></div>
          <label htmlFor="payments-search">Search receipt / invoice / allottee<input id="payments-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} /></label>
          <label htmlFor="payments-from">Payment From<input id="payments-from" className="inp" type="date" max={filters.to || undefined} value={filters.from} onChange={e => setFilters(f => ({ ...f, from: e.target.value }))} /></label>
          <label htmlFor="payments-to">Payment To<input id="payments-to" className="inp" type="date" min={filters.from || undefined} value={filters.to} onChange={e => setFilters(f => ({ ...f, to: e.target.value }))} /></label>
          <button className="btn-ghost" style={{ padding: "9px 14px", fontSize: 12 }} onClick={() => setFilters({ tenant: "all", year: "all", month: "all", search: "", from: "", to: "" })}>Reset</button>
        </div>
        <Pagination pagination={pagination} label="payments" />
      </div>
      <div className="card table-scroll" tabIndex={0} role="region" aria-label="Scrollable records" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr style={{ borderBottom: "1px solid #21262d" }}>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>DATE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>INVOICE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>ALLOTTEE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>BILL MONTH</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>AMOUNT</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PENALTY PAID</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>RECEIPT NO</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map(p => (
              <tr key={p.id} className="row-hover" style={{ borderBottom: "1px solid #21262d" }}>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13 }}>{formatDate(p.payment_date)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", color: "#f0a500" }}>{p.bill_invoice}</td>
                <td style={{ padding: "10px 14px" }}>{p.bill_tenant_name}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13 }}>{p.bill_period}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#22c55e", fontWeight: 700 }}>{formatCurrency(p.amount)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: p.penalty_paid > 0 ? "#ef4444" : "#8b949e" }}>{p.penalty_paid > 0 ? formatCurrency(p.penalty_paid) : "—"}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13 }}>{p.receipt_no || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

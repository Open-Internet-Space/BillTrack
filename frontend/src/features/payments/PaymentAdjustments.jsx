import { useState, useEffect } from "react";
import Pagination, { usePagination } from "../../Pagination";
import FilterBar, { matchesSearch, withinDates } from "../../Filters";
import RefreshButton from "../../RefreshButton";
import { AdjustmentBill } from "./AdjustmentBill.jsx";

export function PaymentAdjustments({ payments, bills, refresh, refreshing }) {
  const [vendor, setVendor] = useState("");
  const [filters, setFilters] = useState({ search: "", year: "all", month: "all", from: "", to: "" });
  const years = [...new Set(payments.map(p => p.bill_year).filter(Boolean))].sort((a, b) => b - a);
  const months = [...new Set(payments.map(p => p.bill_month).filter(Boolean))].sort((a, b) => a - b);
  const vendors = [...new Map(payments.map(p => [String(p.bill_tenant), (p.bill_tenant_display_name || p.bill_tenant_name)])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));
  const billsById = new Map(bills.map(b => [b.id, b]));
  const groups = new Map();
  payments.filter(p => String(p.bill_tenant) === vendor).forEach(p => {
    if (!groups.has(p.bill)) groups.set(p.bill, []);
    groups.get(p.bill).push(p);
  });

  const matchingGroups = [...groups.entries()].map(([id, splits]) => [id, splits.filter(p =>
    matchesSearch(filters.search, p.receipt_no, p.bill_invoice, billsById.get(id)?.invoice_no, billsById.get(id)?.dispatch_ref_no)
    && (filters.year === "all" || String(p.bill_year ?? billsById.get(id)?.year) === filters.year)
    && (filters.month === "all" || String(p.bill_month ?? billsById.get(id)?.month) === filters.month)
    && withinDates(p.payment_date, filters.from, filters.to))]).filter(([, splits]) => splits.length);
  const pagination = usePagination(matchingGroups);
  const { setPage } = pagination;
  useEffect(() => setPage(1), [vendor, filters, setPage]);

  return (
    <div>
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 className="page-title">Payment Adjustments</h1>
        <RefreshButton onRefresh={refresh} busy={refreshing} />
      </div>
      <FilterBar label="Adjustment filters" onReset={() => setFilters({ search: "", year: "all", month: "all", from: "", to: "" })}>
        <div>
        <label htmlFor="adjustment-vendor">Allottee</label>
        <select id="adjustment-vendor" className="inp" style={{ maxWidth: 360 }} value={vendor} onChange={e => setVendor(e.target.value)}>
          <option value="">Select an allottee</option>
          {vendors.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        </div>
        <label htmlFor="adjustments-search">Search invoice / receipt / reference<input id="adjustments-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} /></label>
        <label htmlFor="adjustments-year">Bill Year<select id="adjustments-year" className="inp" value={filters.year} onChange={e => setFilters(f => ({ ...f, year: e.target.value }))}><option value="all">All Years</option>{years.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
        <label htmlFor="adjustments-month">Bill Month<select id="adjustments-month" className="inp" value={filters.month} onChange={e => setFilters(f => ({ ...f, month: e.target.value }))}><option value="all">All Months</option>{months.map(month => <option key={month} value={month}>{new Date(2000, month - 1, 1).toLocaleString("en-IN", { month: "short" })}</option>)}</select></label>
        <label htmlFor="adjustments-from">Payment From<input id="adjustments-from" className="inp" type="date" max={filters.to || undefined} value={filters.from} onChange={e => setFilters(f => ({ ...f, from: e.target.value }))} /></label>
        <label htmlFor="adjustments-to">Payment To<input id="adjustments-to" className="inp" type="date" min={filters.from || undefined} value={filters.to} onChange={e => setFilters(f => ({ ...f, to: e.target.value }))} /></label>
      </FilterBar>
      <p style={{ color: "#8b949e", fontSize: 12 }}>Filters narrow the payment entries shown; bill totals include all payments.</p>
      {vendor && <Pagination pagination={pagination} label="bills" />}
      {vendor && (matchingGroups.length ? pagination.pageRows.map(([billId, splits]) => {
        const bill = billsById.get(billId);
        return <AdjustmentBill key={billId} bill={bill} splits={splits} allSplits={groups.get(billId)} resetKey={filters} />;
      }) : <div className="card" style={{ color: "#8b949e" }}>No matching payments for this allottee.</div>)}
    </div>
  );
}

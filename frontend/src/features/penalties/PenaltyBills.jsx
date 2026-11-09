import { Fragment, useState, useEffect } from "react";
import Pagination, { usePagination } from "../../Pagination";
import { matchesSearch, withinDates } from "../../Filters";
import { formatCurrency, formatDate } from "../../shared/format.js";

export function PenaltyBills({ bills, period }) {
  const [filters, setFilters] = useState({ search: "", from: "", to: "" });
  const filteredBills = bills.filter(b => matchesSearch(filters.search, b.invoice_no, b.dispatch_ref_no)
    && withinDates(b.due_date, filters.from, filters.to));
  const pagination = usePagination(filteredBills, filters);
  const { setPage } = pagination;
  useEffect(() => setPage(1), [period, setPage]);
  const [expandedBill, setExpandedBill] = useState(null);
  return <>
    <div className="record-filters" role="group" aria-label="Penalty bill filters">
      <label htmlFor="penalty-bills-search">Search invoice / reference<input id="penalty-bills-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} /></label>
      <label htmlFor="penalty-bills-from">Due From<input id="penalty-bills-from" className="inp" type="date" max={filters.to || undefined} value={filters.from} onChange={e => setFilters(f => ({ ...f, from: e.target.value }))} /></label>
      <label htmlFor="penalty-bills-to">Due To<input id="penalty-bills-to" className="inp" type="date" min={filters.from || undefined} value={filters.to} onChange={e => setFilters(f => ({ ...f, to: e.target.value }))} /></label>
      <button className="btn-ghost" onClick={() => setFilters({ search: "", from: "", to: "" })}>Reset</button>
    </div>
    <Pagination pagination={pagination} label="bills" />
    <table><thead><tr style={{ color: "#8b949e", fontSize: 12 }}>
      {['INVOICE', 'PERIOD', 'DUE DATE', 'BALANCE', 'DAYS OVERDUE', 'PENALTY', 'TOTAL DUE', 'DETAILS'].map(label => <th key={label} style={{ padding: "9px 10px" }}>{label}</th>)}
    </tr></thead><tbody>{pagination.pageRows.map(bill => <Fragment key={bill.id}><tr style={{ borderTop: "1px solid #21262d" }}>
      <td style={{ padding: "9px 10px", color: "#f0a500" }}>{bill.invoice_no || "[Pending]"}</td>
      <td style={{ padding: "9px 10px" }}>{bill.month_name} {bill.year}</td>
      <td style={{ padding: "9px 10px" }}>{formatDate(bill.due_date)}</td>
      <td style={{ padding: "9px 10px" }}>{formatCurrency(bill.balance_due)}</td>
      <td style={{ padding: "9px 10px", color: "#f87171" }}>{bill.days_overdue}d</td>
      <td style={{ padding: "9px 10px", color: "#f87171" }}>{formatCurrency(bill.penalty)}</td>
      <td style={{ padding: "9px 10px", fontWeight: 700 }}>{formatCurrency(Number(bill.balance_due || 0) + Number(bill.penalty || 0))}</td>
      <td style={{ padding: "9px 10px" }}><button className="btn-ghost" onClick={() => setExpandedBill(expandedBill === bill.id ? null : bill.id)}>{expandedBill === bill.id ? "Hide" : "Calculation"}</button></td>
    </tr>{expandedBill === bill.id && <tr><td colSpan={8} style={{ padding: "9px 10px", color: "#8b949e" }}>Internal calculation: {bill.penalty_calculation?.formula} = {formatCurrency(bill.penalty_calculation?.result || 0)}; balance {formatCurrency(bill.penalty_calculation?.principal || 0)}, {bill.penalty_calculation?.days} days from {bill.penalty_calculation?.start_date}.</td></tr>}</Fragment>)}</tbody></table>
  </>;
}

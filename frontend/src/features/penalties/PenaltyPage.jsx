import { Fragment, useState, useEffect } from "react";
import Pagination, { usePagination } from "../../Pagination";
import FilterBar from "../../Filters";
import RefreshButton from "../../RefreshButton";
import { formatCurrency } from "../../shared/format.js";
import { PenaltyBills } from "./PenaltyBills.jsx";

export function PenaltyPage({ bills, tenants, refresh, refreshing }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("all");
  const [period, setPeriod] = useState({ year: "all", month: "all" });
  const years = [...new Set(bills.map(b => b.year).filter(Boolean))].sort((a, b) => b - a);
  const months = [...new Set(bills.map(b => b.month).filter(Boolean))].sort((a, b) => a - b);
  const [expandedTenant, setExpandedTenant] = useState(null);
  const types = [...new Set(tenants.map(t => t.type).filter(Boolean))];
  const overdue = bills.filter(b => b.days_overdue > 0 && b.status !== "Paid"
    && (period.year === "all" || String(b.year) === period.year)
    && (period.month === "all" || String(b.month) === period.month));
  const vendors = Object.values(overdue.reduce((groups, b) => {
    const vendor = groups[b.tenant] ||= { ...b, bills: [], bill_count: 0, balance_due: 0, penalty: 0, days_overdue: 0 };
    vendor.bills.push(b);
    vendor.bill_count++;
    vendor.balance_due += Number(b.balance_due || 0);
    vendor.penalty += Number(b.penalty || 0);
    vendor.days_overdue = Math.max(vendor.days_overdue, Number(b.days_overdue || 0));
    return groups;
  }, {})).filter(b => b.tenant_name?.toLowerCase().includes(name.trim().toLowerCase()))
    .filter(b => type === "all" || b.tenant_type === type);
  const totalPenalty = vendors.reduce((s, b) => s + b.penalty, 0);
  const pagination = usePagination(vendors);
  const { pageSize, setPage, pageRows: pageVendors } = pagination;

  useEffect(() => setPage(1), [name, type, period, pageSize, setPage]);

  return (
    <div>
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 className="page-title">Penalty Register</h1>
        <RefreshButton onRefresh={refresh} busy={refreshing} />
      </div>
      <div style={{ background: "#ef444422", border: "1px solid #ef4444", borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
        <span style={{ fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#f87171" }}>Total Penalty Due: <strong>{formatCurrency(totalPenalty)}</strong></span>
      </div>
      <FilterBar label="Penalty filters" onReset={() => { setName(""); setType("all"); setPeriod({ year: "all", month: "all" }); }}>
        <label htmlFor="penalty-search">Search allottee name<input id="penalty-search" className="inp" type="search" aria-label="Search allottee name" value={name} onChange={e => setName(e.target.value)} /></label>
        <label htmlFor="penalty-type">Allottee Type<select id="penalty-type" className="inp" aria-label="Filter by allottee type" value={type} onChange={e => setType(e.target.value)}>
          <option value="all">All types</option>
          {types.map(t => <option key={t} value={t}>{t}</option>)}
        </select></label>
        <label htmlFor="penalty-year">Bill Year<select id="penalty-year" className="inp" value={period.year} onChange={e => setPeriod(p => ({ ...p, year: e.target.value }))}><option value="all">All Years</option>{years.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
        <label htmlFor="penalty-month">Bill Month<select id="penalty-month" className="inp" value={period.month} onChange={e => setPeriod(p => ({ ...p, month: e.target.value }))}><option value="all">All Months</option>{months.map(month => <option key={month} value={month}>{new Date(2000, month - 1, 1).toLocaleString("en-IN", { month: "short" })}</option>)}</select></label>
      </FilterBar>
      <Pagination pagination={pagination} label="allottees" />
      <div className="card table-scroll" tabIndex={0} role="region" aria-label="Scrollable records" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr style={{ borderBottom: "1px solid #21262d" }}>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>ALLOTTEE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>OVERDUE BILLS</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>BALANCE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>DAYS OVERDUE</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>PENALTY</th>
              <th style={{ padding: "11px 14px", fontSize: 12, color: "#8b949e" }}>TOTAL PAYABLE</th>
            </tr>
          </thead>
          <tbody>
            {pageVendors.map(b => (
              <Fragment key={b.tenant}>
              <tr className="row-hover" style={{ borderBottom: "1px solid #21262d" }}>
                <td style={{ padding: "10px 14px" }}><button aria-expanded={expandedTenant === b.tenant} onClick={() => setExpandedTenant(expandedTenant === b.tenant ? null : b.tenant)} style={{ background: "none", border: 0, color: "#e6edf3", padding: 0, textAlign: "left", font: "inherit", fontWeight: 600 }}>{expandedTenant === b.tenant ? "▾ " : "▸ "}{b.tenant_name}</button><br /><span style={{ fontSize: 11, color: "#8b949e" }}>{b.tenant_type}</span></td>
                <td style={{ padding: "10px 14px" }}>{b.bill_count}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", color: "#f59e0b" }}>{formatCurrency(b.balance_due)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", color: "#f87171", fontWeight: 700 }}>{b.days_overdue}d</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", color: "#f87171", fontWeight: 700 }}>{formatCurrency(b.penalty)}</td>
                <td style={{ padding: "10px 14px", fontFamily: "'JetBrains Mono',monospace", fontWeight: 700 }}>{formatCurrency(b.balance_due + b.penalty)}</td>
              </tr>
              {expandedTenant === b.tenant && <tr><td colSpan={6} style={{ padding: "8px 14px 14px", background: "#0d1117" }}>
                <PenaltyBills bills={b.bills} period={period} />
              </td></tr>}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

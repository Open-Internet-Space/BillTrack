import Pagination, { usePagination } from "../../Pagination";
import RefreshButton from "../../RefreshButton";
import { formatCurrency, formatDate } from "../../shared/format.js";

export function Dashboard({ stats, bills, tenants, onOpenBills, refresh, refreshing }) {
  const billed = Number(stats.total_billed || 0);
  const collected = Number(stats.total_collected || 0);
  const outstanding = Number(stats.total_outstanding || 0);
  const penalty = Number(stats.total_penalty || 0);
  const collectionRate = billed ? Math.min(100, Math.round(collected / billed * 100)) : 0;
  const statCards = [
    { label: "Total billed", value: formatCurrency(billed), color: "#60a5fa", note: "Across all bills" },
    { label: "Collected", value: formatCurrency(collected), color: "#22c55e", note: `${collectionRate}% of total billed` },
    { label: "Outstanding", value: formatCurrency(outstanding + penalty), color: "#f87171", note: `${formatCurrency(penalty)} penalty included` },
    { label: "Pending bills", value: Number(stats.unpaid_count || 0) + Number(stats.partial_count || 0), color: "#f0a500", note: `${stats.unpaid_count || 0} unpaid · ${stats.partial_count || 0} partial` },
  ];
  const overdueVendors = Object.values(bills.filter(b => Number(b.days_overdue) > 0 && b.status !== "Paid").reduce((groups, b) => {
    const vendor = groups[b.tenant] ||= { ...b, bill_count: 0, balance_due: 0, penalty: 0, days_overdue: 0 };
    vendor.bill_count++;
    vendor.balance_due += Number(b.balance_due || 0);
    vendor.penalty += Number(b.penalty || 0);
    vendor.days_overdue = Math.max(vendor.days_overdue, Number(b.days_overdue || 0));
    return groups;
  }, {})).sort((a, b) => b.days_overdue - a.days_overdue);
  const overduePagination = usePagination(overdueVendors);
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const upcomingBills = bills.filter(b => b.issue_date && b.status !== "Paid" && b.due_date && b.due_date >= today)
    .sort((a, b) => a.due_date.localeCompare(b.due_date));
  const upcomingPagination = usePagination(upcomingBills);

  return (
    <div className="dashboard-page">
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "end", marginBottom: 24 }}>
        <h1 className="page-title">Dashboard</h1>
        <div className="toolbar-actions" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ color: "#8b949e", fontSize: 13 }}>{tenants.filter(t => t.active).length} active allottees</span>
          <RefreshButton onRefresh={refresh} busy={refreshing} />
        </div>
      </div>
      <div className="metrics-grid">
        {statCards.map(s => <div key={s.label} className="card">
          <div className="metric-label">{s.label}</div>
          <div className="metric-value" style={{ color: s.color }}>{s.value}</div>
          <div className="metric-note">{s.note}</div>
        </div>)}
      </div>
      <div className="dashboard-sections">
        <div className="card collection-summary">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}><strong style={{ fontSize: 16, fontWeight: 600 }}>Collection progress</strong><span style={{ color: "#22c55e", fontFamily: "'JetBrains Mono',monospace" }}>{collectionRate}%</span></div>
          <div style={{ height: 9, borderRadius: 8, background: "#30363d", overflow: "hidden", marginBottom: 12 }}><div style={{ width: `${collectionRate}%`, height: "100%", background: "#22c55e", borderRadius: 8 }} /></div>
          <div style={{ display: "flex", justifyContent: "space-between", color: "#8b949e", fontSize: 12 }}><span>{formatCurrency(collected)} collected</span><span>{formatCurrency(outstanding)} remaining</span></div>
        </div>
        <div className="card dashboard-list-card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="section-heading"><strong>Most overdue allottees</strong><span>{overdueVendors.length} allottees</span></div>
          <div className="dashboard-list" role="region" aria-label="Most overdue allottees" tabIndex={0}>
          {overdueVendors.length ? overduePagination.pageRows.map(b => <button className="dashboard-entry" key={b.tenant} onClick={() => onOpenBills({ tenant: b.tenant })} aria-label={`View bills for ${b.tenant_name}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, padding: "12px 20px", borderBottom: "1px solid #21262d", alignItems: "center" }}>
            <div style={{ minWidth: 0 }}><div style={{ fontSize: 14, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.tenant_name}</div><div style={{ color: "#8b949e", fontSize: 12 }}>{b.bill_count} overdue {b.bill_count === 1 ? "bill" : "bills"}</div></div>
            <div style={{ textAlign: "right" }}><div style={{ color: "#f87171", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>{b.days_overdue}d overdue</div><div style={{ color: "#8b949e", fontSize: 12 }}>{formatCurrency(b.balance_due + b.penalty)}</div></div>
          </button>) : <div style={{ padding: 22, color: "#8b949e", fontSize: 13 }}>No overdue bills.</div>}
          </div>
          <div style={{ padding: "0 20px" }}><Pagination pagination={overduePagination} label="overdue allottees" /></div>
        </div>
        <div className="card dashboard-list-card" style={{ padding: 0, overflow: "hidden" }}>
          <div className="section-heading"><strong>Upcoming due dates</strong><span>{upcomingBills.length} bills</span></div>
          <div className="dashboard-list" role="region" aria-label="Upcoming due dates" tabIndex={0}>
          {upcomingBills.length ? upcomingPagination.pageRows.map(b => <button className="dashboard-entry" key={b.id} onClick={() => onOpenBills({ tenant: b.tenant, billId: b.id })} aria-label={`View bill ${b.invoice_no || b.id} for ${b.tenant_name}`} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, padding: "12px 20px", borderBottom: "1px solid #21262d", alignItems: "center" }}>
            <div style={{ minWidth: 0 }}><div style={{ fontSize: 14, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{b.tenant_name}</div><div style={{ color: "#8b949e", fontSize: 11 }}>{b.invoice_no || `${b.month_name || "Bill"} ${b.year}`}</div></div>
            <div style={{ textAlign: "right" }}><div style={{ color: "#f0a500", fontFamily: "'JetBrains Mono',monospace", fontSize: 12 }}>{formatDate(b.due_date)}</div><div style={{ color: "#8b949e", fontSize: 11 }}>{formatCurrency(Number(b.balance_due || 0))}</div></div>
          </button>) : <div style={{ padding: 22, color: "#8b949e", fontSize: 13 }}>No upcoming due dates.</div>}
          </div>
          <div style={{ padding: "0 20px" }}><Pagination pagination={upcomingPagination} label="upcoming bills" /></div>
        </div>
      </div>
    </div>
  );
}

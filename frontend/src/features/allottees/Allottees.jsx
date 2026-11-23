import { allotteeLabel } from "../../shared/format.js";
import { useState } from "react";
import Pagination, { usePagination } from "../../Pagination";
import FilterBar, { matchesSearch } from "../../Filters";
import RefreshButton from "../../RefreshButton";
import { TypeBadge } from "../../shared/Badges.jsx";

export function Allottees({ tenants, onOpenBills, onOpenDraft, onOpenEstate, setModal, refresh, refreshing }) {
  const [filters, setFilters] = useState({ search: "", type: "all", active: "all", sort: "name" });
  const tenantRows = Array.isArray(tenants) ? tenants : [];
  const types = [...new Set(tenantRows.map(t => t.type).filter(Boolean))].sort();
  const filteredRows = tenantRows.filter(t => matchesSearch(filters.search, allotteeLabel(t), t.uuid, t.contact, t.email, t.gstin)
    && (filters.type === "all" || t.type === filters.type)
    && (filters.active === "all" || Boolean(t.active) === (filters.active === "active")));
  const monthNames = "January February March April May June July August September October November December".split(" ");
  const billedPeriod = allottee => {
    const [month, year] = (allottee.last_billed_month || "").split(" ");
    const monthIndex = monthNames.indexOf(month);
    return monthIndex < 0 ? 0 : Number(year) * 12 + monthIndex;
  };
  filteredRows.sort((a, b) => {
    const periodOrder = filters.sort === "name" ? 0
      : (billedPeriod(a) - billedPeriod(b)) * (filters.sort === "billed_desc" ? -1 : 1);
    return periodOrder || allotteeLabel(a).localeCompare(allotteeLabel(b));
  });
  const pagination = usePagination(filteredRows, filters);
  return (
    <div>
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", marginBottom: 22 }}>
        <h1 className="page-title">Allottees</h1>
        <div className="toolbar-actions" style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <RefreshButton onRefresh={refresh} busy={refreshing} />
        <button className="btn-primary" onClick={() => setModal({ type: "addTenant" })}>+ Add Allottee</button>
        </div>
      </div>
      <FilterBar label="Allottee filters" onReset={() => setFilters({ search: "", type: "all", active: "all", sort: "name" })}>
        <label htmlFor="tenants-search">Search name / contact<input id="tenants-search" className="inp" type="search" value={filters.search} onChange={e => setFilters(f => ({ ...f, search: e.target.value }))} /></label>
        <label htmlFor="tenants-type">Allottee Type<select id="tenants-type" className="inp" value={filters.type} onChange={e => setFilters(f => ({ ...f, type: e.target.value }))}><option value="all">All Types</option>{types.map(type => <option key={type} value={type}>{type}</option>)}</select></label>
        <label htmlFor="tenants-active">Status<select id="tenants-active" className="inp" value={filters.active} onChange={e => setFilters(f => ({ ...f, active: e.target.value }))}><option value="all">All Status</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
        <label htmlFor="tenants-sort">Sort by<select id="tenants-sort" className="inp" value={filters.sort} onChange={e => setFilters(f => ({ ...f, sort: e.target.value }))}><option value="name">Name (A–Z)</option><option value="billed_asc">Last billed: oldest first</option><option value="billed_desc">Last billed: newest first</option></select></label>
      </FilterBar>
      <Pagination pagination={pagination} label="allottees" />
      <div className="card table-scroll" tabIndex={0} role="region" aria-label="Scrollable records" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr style={{ borderBottom: "1px solid #21262d" }}>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>NAME</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>TYPE</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>CONTACT</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>GSTIN</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>LAST BILLED MONTH</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>TERMS</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>STATUS</th>
              <th style={{ padding: "12px 16px", fontSize: 12, color: "#8b949e" }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {pagination.pageRows.map(t => (
              <tr key={t.id} className="row-hover" style={{ borderBottom: "1px solid #21262d" }}>
                <td style={{ padding: "12px 16px", fontWeight: 600 }}>{allotteeLabel(t)}</td>
                <td style={{ padding: "12px 16px" }}><TypeBadge type={t.type} /></td>
                <td style={{ padding: "12px 16px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#8b949e" }}>
                  {t.contact_not_provided ? "Not Provided" : t.contact || "-"}<br /><span style={{ fontSize: 11 }}>{t.email_not_provided ? "Not Provided" : t.email || "-"}</span>
                </td>
                <td style={{ padding: "12px 16px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#8b949e" }}>{t.gstin_not_provided ? "Not Provided" : t.gstin || "-"}</td>
                <td style={{ padding: "12px 16px" }}>{t.last_billed_month || "Never billed"}</td>
                <td style={{ padding: "12px 16px", fontFamily: "'JetBrains Mono',monospace", fontSize: 13, color: "#8b949e" }}>Due 5d after receipt<br /><span style={{ fontSize: 12 }}>{t.penalty_type || "system"} / {t.custom_penalty_frequency || "system"}</span></td>
                <td style={{ padding: "12px 16px", fontSize: 11, color: t.active ? "#22c55e" : "#ef4444", fontWeight: 700 }}>{t.active ? "● ACTIVE" : "○ INACTIVE"}</td>
                <td style={{ padding: "12px 16px" }}><div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}><button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => setModal({ type: "editTenant", data: t })}>Edit</button>{onOpenEstate && <button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => onOpenEstate({ tenant: t.id, tenantName: t.name })}>Shop history</button>}<button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => onOpenDraft({allotteeId:t.id})}>Email Draft</button><button className="btn-ghost" style={{ padding: "4px 10px", fontSize: 11 }} aria-label={`Raise bill for ${allotteeLabel(t)}`} disabled={!t.active} title={t.active ? "Open this allottee's bills" : "Activate this allottee before raising bills"} onClick={() => onOpenBills({ tenant: t.id })}>Raise Bill</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

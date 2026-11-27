import { allotteeLabel } from "../../shared/format.js";
import { BillFilters } from "./BillFilters";
import { BillTable } from "./BillTable";
import { useState, useEffect, useMemo } from "react";
import { usePagination } from "../../Pagination";
import { matchesSearch } from "../../Filters";
import RefreshButton from "../../RefreshButton";
import API from "../../api";
import { openPrintDocument } from "../../shared/printDocument";

const periodOrder = (a, b) => b.year - a.year || b.month - a.month;
const assessmentMonth = new Intl.DateTimeFormat('en', { month: 'short', timeZone: 'UTC' });

export function Bills({ user, bills, tenants, setBills, setModal, refresh, revision, showToast, onOpenDraft, onOpenEstate, initialContext }) {
  const billRows = useMemo(() => Array.isArray(bills) ? bills : [], [bills]);
  const [extensions, setExtensions] = useState({ rows: [], error: '', loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setExtensions(previous => ({ ...previous, error: '', loading: true }));
    API.getAll('/estate-charges/?kind=extension_fee')
      .then(rows => { if (active) setExtensions({ rows, error: '', loading: false }); })
      .catch(error => { if (active) setExtensions(previous => ({ ...previous, error: error.message, loading: false })); });
    return () => { active = false; };
  }, [revision, retry]);
  const rows = useMemo(() => {
    const tenantTypes = new Map(tenants.map(tenant => [tenant.id, tenant.type]));
    const demands = extensions.rows.filter(charge => charge.kind === 'extension_fee').map(charge => {
      const [year, month] = charge.assessed_on.split('-').map(Number);
      return { ...charge, id: `extension-${charge.id}`, charge, year, month,
        month_name: assessmentMonth.format(new Date(`${charge.assessed_on}T00:00:00Z`)),
        invoice_no: 'Extension fee demand', tenant_display_name: charge.register_label,
        tenant_type: tenantTypes.get(charge.tenant) };
    });
    return [...billRows, ...demands].sort(periodOrder);
  }, [billRows, extensions.rows, tenants]);
  const [refreshing, setRefreshing] = useState(false);
  const [filters, setFilters] = useState({ tenant: String(initialContext?.tenant || "all"), status: "all", receipt: "all", search: "", type: "all", year: "all", month: "all", billId: initialContext?.billId || null, allotment: initialContext?.allotment || null, registerLabel: initialContext?.registerLabel || '' });
  const [selectedBillIds, setSelectedBillIds] = useState([]);
  const tenantOptions = useMemo(() => {
    const map = new Map(tenants.map(t => [String(t.id), allotteeLabel(t)]));
    rows.forEach(b => {
      if (b.tenant && !map.has(String(b.tenant))) map.set(String(b.tenant), (b.tenant_display_name || b.tenant_name));
    });
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [rows, tenants]);
  const yearOptions = useMemo(() => {
    return Array.from(new Set(rows.map(b => b.year))).filter(Boolean).sort((a, b) => b - a);
  }, [rows]);
  const monthOptions = useMemo(() => {
    const map = new Map();
    rows.forEach(b => {
      if (b.month) map.set(String(b.month), b.month_name || String(b.month));
    });
    return Array.from(map.entries()).sort((a, b) => Number(a[0]) - Number(b[0]));
  }, [rows]);
  const types = [...new Set(rows.map(b => b.tenant_type).filter(Boolean))].sort();
  const filteredBillRows = useMemo(() => {
    return rows.filter(b => {
      if (!matchesSearch(filters.search, b.invoice_no, b.dispatch_ref_no, (b.tenant_display_name || b.tenant_name), b.charge?.description, b.charge?.authority_reference)) return false;
      if (filters.type !== "all" && b.tenant_type !== filters.type) return false;
      if (filters.billId && b.id !== filters.billId) return false;
      if (filters.allotment && ![b.allotment, b.charge?.renewal_term].some(id => String(id) === String(filters.allotment))) return false;
      if (filters.tenant !== "all" && String(b.tenant) !== filters.tenant) return false;
      if (filters.status !== "all" && b.status !== filters.status) return false;
      if (filters.receipt !== "all" && (b.charge || Boolean(b.billing_policy === 'notices_368_369' ? b.email_dispatched_at : b.issue_date) !== (filters.receipt === "confirmed"))) return false;
      if (filters.year !== "all" && String(b.year) !== filters.year) return false;
      if (filters.month !== "all" && String(b.month) !== filters.month) return false;
      return true;
    });
  }, [rows, filters]);
  const changeFilter = (field, value) => setFilters(previous => ({ ...previous, [field]: value, billId: null,
    ...(field === 'tenant' ? { allotment: null, registerLabel: '' } : {}) }));
  const selectedSet = useMemo(() => new Set(selectedBillIds), [selectedBillIds]);
  const pagination = usePagination(filteredBillRows);
  const { pageSize, setPage, pageRows } = pagination;
  const selectablePageRows = pageRows.filter(b => !b.charge);
  const allSelected = selectablePageRows.length > 0 && selectablePageRows.every(b => selectedSet.has(b.id));

  useEffect(() => {
    setPage(1);
  }, [filters, pageSize, setPage]);

  useEffect(() => {
    const validIds = new Set(filteredBillRows.map(b => b.id));
    setSelectedBillIds(prev => prev.filter(id => validIds.has(id)));
  }, [filteredBillRows]);

  /*
  const downloadPDF = async (billId, invoiceNo) => {
    try {
      const res = await fetch(`${API_URL}/bills/${billId}/pdf/`, {
        headers: API.headers()
      });
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${invoiceNo}.pdf`;
      a.click();
    } catch (err) {
      alert("PDF download failed");
    }
  };
  */

  const openPrint = path => openPrintDocument(path, showToast);
  const openInvoice = (billId) => openPrint(`/invoice/${billId}/`);
  const toggleBillSelection = (billId) => {
    setSelectedBillIds(prev =>
      prev.includes(billId) ? prev.filter(id => id !== billId) : [...prev, billId]
    );
  };
  const toggleAllBills = () => {
    const pageIds = selectablePageRows.map(b => b.id);
    setSelectedBillIds(prev => allSelected
      ? prev.filter(id => !pageIds.includes(id))
      : Array.from(new Set([...prev, ...pageIds]))
    );
  };
  const openBulkPrint = () => {
    if (!selectedBillIds.length) return;
    openPrint(`/invoice/bulk/?ids=${selectedBillIds.join(",")}`);
  };
  const deleteBill = async (bill) => {
    try {
      await API.delete(`/bills/${bill.id}/`);
      showToast?.("Bill deleted");
      refresh?.();
    } catch (err) {
      if (err.uncertain) refresh?.();
      showToast?.(err.message || "Delete failed", false);
    }
  };
  const refreshBills = async () => {
    setRetry(value => value + 1);
    setRefreshing(true);
    try {
      const latestBills = await API.getAll("/bills/");
      setBills(latestBills);
      showToast?.("Bills refreshed");
    } catch (err) {
      showToast?.(err.message || "Could not refresh bills", false);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div>
      <div className="page-toolbar" style={{ display: "flex", justifyContent: "space-between", marginBottom: 22 }}>
        <h1 className="page-title">Bills</h1>
        <div className="toolbar-actions" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {onOpenDraft && <button className="btn-ghost" disabled={!selectedBillIds.length} onClick={()=>{
            const selected=billRows.filter(b=>selectedBillIds.includes(b.id));
            if(!selected.length||selected.some(b=>b.tenant!==selected[0].tenant)){showToast?.("Select bills belonging to one allottee only.",false);return;}
            onOpenDraft({allotteeId:selected[0].tenant,billIds:selectedBillIds});
          }}>Draft Email</button>}
          <RefreshButton onRefresh={refreshBills} busy={refreshing} />
          <button
            className="btn-ghost"
            style={{ padding: "8px 14px", fontSize: 12, opacity: selectedBillIds.length ? 1 : 0.55, cursor: selectedBillIds.length ? "pointer" : "not-allowed" }}
            onClick={openBulkPrint}
            disabled={!selectedBillIds.length}
          >
            Print Selected ({selectedBillIds.length})
          </button>
          <button className="btn-primary" onClick={() => setModal({ type: "addBill", tenant: filters.tenant !== "all" ? filters.tenant : undefined, allotment: filters.allotment })}>+ Raise Bill</button>
        </div>
      </div>
      {extensions.loading && !extensions.rows.length && <p role="status">Loading extension fee demands…</p>}
      {extensions.error && <div role="alert">Could not load extension fee demands. {extensions.error} <button className="btn-ghost" onClick={() => setRetry(value => value + 1)}>Retry extension fee demands</button></div>}
      <BillFilters filters={filters} billRows={billRows} setFilters={setFilters} changeFilter={changeFilter} types={types} tenantOptions={tenantOptions} yearOptions={yearOptions} monthOptions={monthOptions} pagination={pagination} />
      <BillTable user={user} allSelected={allSelected} toggleAllBills={toggleAllBills} canSelectAll={selectablePageRows.length > 0} pageRows={pageRows} selectedSet={selectedSet} toggleBillSelection={toggleBillSelection} openInvoice={openInvoice} setModal={setModal} deleteBill={deleteBill}
        openDemand={charge => openPrintDocument(`/estate-charges/${charge.id}/demand/`, showToast, 'extension fee demand')}
        openCharge={charge => onOpenEstate({ tenant: charge.tenant, allotment: charge.allotment, charge: charge.id })} />
    </div>
  );
}

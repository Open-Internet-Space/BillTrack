import { BillFilters } from "./BillFilters";
import { BillTable } from "./BillTable";
import { useState, useEffect, useMemo } from "react";
import { usePagination } from "../../Pagination";
import { matchesSearch } from "../../Filters";
import RefreshButton from "../../RefreshButton";
import API from "../../api";

export function Bills({ bills, tenants, setBills, setModal, refresh, showToast, initialContext }) {
  const billRows = useMemo(() => Array.isArray(bills) ? bills : [], [bills]);
  const [refreshing, setRefreshing] = useState(false);
  const [filters, setFilters] = useState({ tenant: String(initialContext?.tenant || "all"), status: "all", receipt: "all", search: "", type: "all", year: "all", month: "all", billId: initialContext?.billId || null });
  const [selectedBillIds, setSelectedBillIds] = useState([]);
  const tenantOptions = useMemo(() => {
    const map = new Map(tenants.map(t => [String(t.id), t.name]));
    billRows.forEach(b => {
      if (b.tenant && !map.has(String(b.tenant))) map.set(String(b.tenant), b.tenant_name);
    });
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [billRows, tenants]);
  const yearOptions = useMemo(() => {
    return Array.from(new Set(billRows.map(b => b.year))).filter(Boolean).sort((a, b) => b - a);
  }, [billRows]);
  const monthOptions = useMemo(() => {
    const map = new Map();
    billRows.forEach(b => {
      if (b.month) map.set(String(b.month), b.month_name || String(b.month));
    });
    return Array.from(map.entries()).sort((a, b) => Number(a[0]) - Number(b[0]));
  }, [billRows]);
  const types = [...new Set(billRows.map(b => b.tenant_type).filter(Boolean))].sort();
  const filteredBillRows = useMemo(() => {
    return billRows.filter(b => {
      if (!matchesSearch(filters.search, b.invoice_no, b.dispatch_ref_no, b.tenant_name)) return false;
      if (filters.type !== "all" && b.tenant_type !== filters.type) return false;
      if (filters.billId && b.id !== filters.billId) return false;
      if (filters.tenant !== "all" && String(b.tenant) !== filters.tenant) return false;
      if (filters.status !== "all" && b.status !== filters.status) return false;
      if (filters.receipt !== "all" && Boolean(b.issue_date) !== (filters.receipt === "confirmed")) return false;
      if (filters.year !== "all" && String(b.year) !== filters.year) return false;
      if (filters.month !== "all" && String(b.month) !== filters.month) return false;
      return true;
    });
  }, [billRows, filters]);
  const changeFilter = (field, value) => setFilters(previous => ({ ...previous, [field]: value, billId: null }));
  const selectedSet = useMemo(() => new Set(selectedBillIds), [selectedBillIds]);
  const pagination = usePagination(filteredBillRows);
  const { pageSize, setPage, pageRows } = pagination;
  const allSelected = pageRows.length > 0 && pageRows.every(b => selectedSet.has(b.id));

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

  const openPrint = async (path) => {
    let popup;
    try { popup = window.open("about:blank", "_blank"); }
    catch { showToast?.("Allow pop-ups to open the invoice.", false); return; }
    if (!popup) {
      showToast?.("Allow pop-ups to open the invoice.", false);
      return;
    }
    popup.opener = null;
    let objectUrl;
    try {
      const document = await API.document(path);
      if (popup.closed) return;
      objectUrl = URL.createObjectURL(document);
      popup.addEventListener("load", () => URL.revokeObjectURL(objectUrl), { once: true });
      popup.location.replace(objectUrl);
    } catch (error) {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      popup.close();
      showToast?.(error.message || "Invoice could not be loaded.", false);
    }
  };
  const openInvoice = (billId) => openPrint(`/invoice/${billId}/`);
  const toggleBillSelection = (billId) => {
    setSelectedBillIds(prev =>
      prev.includes(billId) ? prev.filter(id => id !== billId) : [...prev, billId]
    );
  };
  const toggleAllBills = () => {
    const pageIds = pageRows.map(b => b.id);
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
    if (!window.confirm(`Delete ${bill.invoice_no || "this bill"}? Payments for this bill will also be deleted.`)) return;
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
          <RefreshButton onRefresh={refreshBills} busy={refreshing} />
          <button
            className="btn-ghost"
            style={{ padding: "8px 14px", fontSize: 12, opacity: selectedBillIds.length ? 1 : 0.55, cursor: selectedBillIds.length ? "pointer" : "not-allowed" }}
            onClick={openBulkPrint}
            disabled={!selectedBillIds.length}
          >
            Print Selected ({selectedBillIds.length})
          </button>
          <button className="btn-primary" onClick={() => setModal({ type: "addBill", tenant: filters.tenant !== "all" ? filters.tenant : undefined })}>+ Raise Bill</button>
        </div>
      </div>
      <BillFilters filters={filters} billRows={billRows} setFilters={setFilters} changeFilter={changeFilter} types={types} tenantOptions={tenantOptions} yearOptions={yearOptions} monthOptions={monthOptions} pagination={pagination} />
      <BillTable allSelected={allSelected} toggleAllBills={toggleAllBills} pageRows={pageRows} selectedSet={selectedSet} toggleBillSelection={toggleBillSelection} openInvoice={openInvoice} setModal={setModal} deleteBill={deleteBill} />
    </div>
  );
}

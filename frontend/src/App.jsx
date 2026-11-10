import { EmailDrafts } from "./features/email-drafts/EmailDrafts.jsx";
import "./branding.css";
import { useState, useEffect, useRef } from "react";
import Reports from "./features/reports/Reports";
import API from "./api";
import { LoginScreen } from "./features/auth/LoginScreen.jsx";
import { Dashboard } from "./features/dashboard/Dashboard.jsx";
import { Allottees } from "./features/allottees/Allottees.jsx";
import { Bills } from "./features/bills/Bills.jsx";
import { PaymentAdjustments } from "./features/payments/PaymentAdjustments.jsx";
import { Payments } from "./features/payments/Payments.jsx";
import { PenaltyPage } from "./features/penalties/PenaltyPage.jsx";
import { TenantForm } from "./features/allottees/TenantForm.jsx";
import { BillForm } from "./features/bills/BillForm.jsx";
import { BillEditForm } from "./features/bills/BillEditForm.jsx";
import { BillDispatchForm } from "./features/bills/BillDispatchForm.jsx";
import { PaymentForm } from "./features/payments/PaymentForm.jsx";
import { ModalOverlay } from "./shared/ModalOverlay.jsx";
import { Sidebar } from "./shared/Sidebar.jsx";
import { ToastNotification } from "./shared/ToastNotification.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [modal, setModal] = useState(null);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);
  const [authState, setAuthState] = useState(() => ({ pending: Boolean(localStorage.getItem("token")), error: "" }));
  const [authRevision, setAuthRevision] = useState(0);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const saveLock = useRef(false);
  const mainRef = useRef(null);
  const focusAfterSave = useRef(false);
  const [revision, setRevision] = useState(0);
  const [loadState, setLoadState] = useState({ loading: true, error: "" });
  const [billContext, setBillContext] = useState(null);

  const [draftContext,setDraftContext]=useState(null);
  const [draftDirty,setDraftDirty]=useState(false);
  const [draftBusy,setDraftBusy]=useState(false);
  const leaveDraft=()=>{
    if(page!=="drafts")return true;
    if(draftBusy){showToast("Wait for the draft operation to finish.",false);return false;}
    return !draftDirty||window.confirm("Discard unsaved draft edits?");
  };
  const navigate=next=>{if(next===page)return;if(leaveDraft()){setDraftDirty(false);setDraftContext(null);setPage(next);}};
  const openDraft=context=>{setDraftContext(context);setPage("drafts");};

  // Data
  const [stats, setStats] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [bills, setBills] = useState([]);
  const [payments, setPayments] = useState([]);
  const loaded = useRef({ tenants: 0, bills: 0, payments: 0 });

  const showToast = (msg, ok = true) => {
    clearTimeout(toastTimer.current);
    setToast({ msg, ok });
    if (ok) toastTimer.current = setTimeout(() => setToast(null), 3000);
  };
  useEffect(() => {
    API.onUnauthorized = () => setSessionExpired(true);
    return () => { API.onUnauthorized = null; clearTimeout(toastTimer.current); };
  }, []);

  useEffect(() => {
    let active = true;
    API.token = localStorage.getItem("token");
    if (!API.token) {
      setAuthState({ pending: false, error: "" });
      return () => { active = false; };
    }
    setAuthState({ pending: true, error: "" });
    API.get("/auth/me/").then(userData => {
      if (!active) return;
      setUser(userData);
      setAuthState({ pending: false, error: "" });
    }).catch(error => {
      if (!active) return;
      if (error.status === 401) {
        API.logout();
        setAuthState({ pending: false, error: "" });
        showToast("Your sign-in has expired. Sign in again to continue.", false);
      } else {
        setAuthState({ pending: false, error: error.message });
      }
    });
    return () => { active = false; };
  }, [authRevision]);

  // Ignore responses from a screen that has since been left.
  useEffect(() => {
    if (!user) return;
    let active = true;
    if (page === "dashboard") loaded.current.payments = 0;
    // shortcut: navigation reuses records for 30s; add live updates if instant cross-session changes are needed.
    const stale = resource => {
      const age = Date.now() - loaded.current[resource];
      return !loaded.current[resource] || age < 0 || age >= 30000;
    };
    const needsTenants = stale("tenants") || page === "dashboard";
    const needsBills = ["dashboard", "bills", "adjustments", "penalty"].includes(page) && (stale("bills") || page === "dashboard");
    const needsPayments = ["payments", "adjustments"].includes(page) && stale("payments");
    setLoadState({ loading: needsTenants || needsBills || needsPayments || page === "dashboard", error: "" });
    Promise.all([
      needsTenants ? API.getAll("/tenants/") : null,
      needsBills ? API.getAll("/bills/") : null,
      page === "dashboard" ? API.get("/dashboard/") : null,
      needsPayments ? API.getAll("/payments/") : null,
    ]).then(([tenantData, billData, dashboardData, paymentData]) => {
      if (!active) return;
      if (tenantData) { setTenants(tenantData.results || tenantData); loaded.current.tenants = Date.now(); }
      if (billData) { setBills(billData); loaded.current.bills = Date.now(); }
      if (dashboardData) setStats(dashboardData);
      if (paymentData) { setPayments(paymentData); loaded.current.payments = Date.now(); }
      setLoadState({ loading: false, error: "" });
    }).catch(error => {
      if (active) setLoadState({ loading: false, error: `${error.message} This screen could not refresh. Retry to load current records.` });
    });
    return () => { active = false; };
  }, [user, page, revision]);

  const refreshData = () => {
    loaded.current = { tenants: 0, bills: 0, payments: 0 };
    setRevision(value => value + 1);
  };
  useEffect(() => {
    if (!modal && focusAfterSave.current) {
      mainRef.current?.focus();
      focusAfterSave.current = false;
    }
  }, [modal]);
  const saveModal = async action => {
    if (saveLock.current) return;
    saveLock.current = true;
    setSaving(true);
    setSaveError("");
    try {
      await action();
      focusAfterSave.current = true;
      setModal(null);
    } catch (error) {
      const uncertain = error.uncertain || error instanceof TypeError || error.status >= 500;
      if (uncertain) refreshData();
      setSaveError(uncertain
        ? "Could not confirm whether the record was saved. Check the records before retrying to avoid a duplicate. Your entries are still here."
        : `${error.message} Your entries are still here${[401, 403].includes(error.status) ? "." : "; correct them and try again."}`);
      if (uncertain && error.reference) setSaveError(message => `${message} Reference: ${error.reference}.`);
    } finally {
      saveLock.current = false;
      setSaving(false);
    }
  };
  const closeModal = () => {
    if (saveLock.current) return;
    setModal(null);
    setSaveError("");
  };
  const openBills = context => {
    setBillContext(context);
    setPage("bills");
  };

  // Login handler
  const handleLogin = async (username, password) => {
    clearTimeout(toastTimer.current);
    setToast(null);
    try {
      const data = await API.login(username, password);
      setSessionExpired(false);
      setAuthState({ pending: false, error: "" });
      setUser(data.user);
      showToast("Login successful");
    } catch (err) {
      showToast(err.message, false);
    }
  };

  const handleLogout = () => {
    if(!leaveDraft())return;
    API.logout();
    loaded.current = { tenants: 0, bills: 0, payments: 0 };
    setUser(null);
    setPage("dashboard");
    setSessionExpired(false);
    setAuthState({ pending: false, error: "" });
    setAuthRevision(value => value + 1);
  };
  const beginSignIn = () => {
    if (saving) return;
    if (modal && !window.confirm("Signing in again will discard unsaved input in the open form. Continue?")) return;
    setModal(null);
    setSaveError("");
    handleLogout();
    showToast("Sign in again to continue. Check saved records before repeating a save.", false);
  };

  if (!user) {
    return <LoginScreen onLogin={handleLogin} toast={toast} onDismissError={() => setToast(null)}
      authState={authState} onRetryAuth={() => setAuthRevision(value => value + 1)} onUseLogin={handleLogout} />;
  }



  return (
    <div className="app-shell" style={{ background: "#0d1117", minHeight: "100vh", color: "#e6edf3", display: "flex" }}>

      {/* Sidebar */}
      <Sidebar user={user} page={page} setBillContext={setBillContext} setPage={navigate} handleLogout={handleLogout} />

      {/* Main */}
      <main ref={mainRef} tabIndex={-1} className="app-main" aria-busy={loadState.loading} style={{ flex: 1, padding: 28 }}>
        {sessionExpired && <div role="alert" className="error-message"><p>Your sign-in has expired. Sign in again to continue. Unsaved form entries remain available until you leave the form.</p><button type="button" className="btn-ghost" onClick={beginSignIn}>Sign in again</button></div>}
        {loadState.loading && <div role="status" className="card">Loading current records…</div>}
        {loadState.error && <div role="alert" className="card load-error"><p>{loadState.error}</p><button className="btn-primary" onClick={refreshData}>Retry</button></div>}
        <div hidden={loadState.loading || Boolean(loadState.error)}>
        {page === "dashboard" && stats && <Dashboard stats={stats} bills={bills} tenants={tenants} onOpenBills={openBills} refresh={refreshData} refreshing={loadState.loading} />}
        {page === "tenants" && <Allottees onOpenDraft={openDraft} tenants={tenants} onOpenBills={openBills} setModal={setModal} refresh={refreshData} refreshing={loadState.loading} showToast={showToast} />}
        {page === "bills" && <Bills onOpenDraft={openDraft} key={`${billContext?.tenant || "all"}-${billContext?.billId || "all"}`} initialContext={billContext} bills={bills} setBills={setBills} tenants={tenants} setModal={setModal} refresh={refreshData} showToast={showToast} />}
        {page === "payments" && <Payments payments={payments} bills={bills} tenants={tenants} setModal={setModal} refresh={refreshData} refreshing={loadState.loading} showToast={showToast} />}
        {page === "adjustments" && <PaymentAdjustments payments={payments} bills={bills} refresh={refreshData} refreshing={loadState.loading} />}
        {page === "penalty" && <PenaltyPage bills={bills} tenants={tenants} refresh={refreshData} refreshing={loadState.loading} />}
        {page === "drafts" && <EmailDrafts context={draftContext} tenants={tenants} onDirty={setDraftDirty} onBusy={setDraftBusy} />}
        {page === "reports" && <Reports api={API} tenants={tenants} refresh={refreshData} />}
        </div>
      </main>

      {/* Modal */}
      {modal && (
        // Modal actions mutate backend state and always call refreshData on
        // success to avoid stale UI snapshots.
        <ModalOverlay onClose={closeModal} saving={saving} error={saveError} sessionExpired={sessionExpired} onSignIn={beginSignIn}>
          {modal.type === "addTenant" && <TenantForm onSave={data => saveModal(async () => {
            await API.post("/tenants/", data);
            refreshData();
            showToast("Allottee added");
          })} onClose={closeModal} />}
          {modal.type === "editTenant" && <TenantForm tenant={modal.data} onSave={data => saveModal(async () => {
            await API.put(`/tenants/${modal.data.id}/`, data);
            refreshData();
            showToast("Allottee updated");
          })} onClose={closeModal} />}
          {modal.type === "addBill" && <BillForm tenants={tenants} initialTenant={modal.tenant} onSave={data => saveModal(async () => {
            const result = data.bulk
              ? await API.post("/bills/bulk-create/", data.payload)
              : await API.post("/bills/", data);
            refreshData();
            if (data.bulk) {
              showToast(`${result.created_count} bill(s) raised${result.skipped_count ? `, ${result.skipped_count} skipped` : ""}`);
            } else {
              showToast("Bill raised");
            }
          })} onClose={closeModal} />}
          {modal.type === "editBill" && <BillEditForm bill={modal.data} onSave={data => saveModal(async () => {
            await API.patch(`/bills/${modal.data.id}/`, data);
            refreshData();
            showToast("Bill updated");
          })} onClose={closeModal} />}
          {modal.type === "recordPayment" && <PaymentForm bill={modal.data} onSave={data => saveModal(async () => {
            await API.post("/payments/", data);
            refreshData();
            showToast("Payment recorded");
          })} onClose={closeModal} />}
          {modal.type === "updateDispatch" && <BillDispatchForm bill={modal.data} onSave={data => saveModal(async () => {
            await API.patch(`/bills/${modal.data.id}/`, data);
            refreshData();
            showToast("Receipt / dispatch details updated");
          })} onClose={closeModal} />}
        </ModalOverlay>
      )}

      {/* Toast */}
      <ToastNotification toast={toast} setToast={setToast} />
    </div>
  );
}

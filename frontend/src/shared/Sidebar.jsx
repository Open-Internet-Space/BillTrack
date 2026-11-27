import { NavIcon } from "./NavIcon.jsx";
import { ProjectIdentity } from "./Branding.jsx";

export function Sidebar({ user, page, onNavigate, handleLogout, canGoBack, canGoForward, onBack, onForward }) {
const navItems = [
    { id: "dashboard", label: "Dashboard" },
    { id: "allotments", label: "Allotments" },
    { id: "bills", label: "Bills" },
    { id: "payments", label: "Payments" },
    { id: "adjustments", label: "Payment Adjustments" },
    { id: "penalty", label: "Penalties" },
    { id: "reports", label: "Reports" },
    { id: "drafts", label: "Email Drafts" },
    { id: "knowledge", label: "Knowledge Base" },
  ];
return (<aside className="app-sidebar" style={{ width: 220, background: "#161b22", borderRight: "1px solid #21262d", display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <div style={{ padding: "24px 20px 16px" }}>
          <img className="sidebar-brand" src="/static/billtrack-logo.webp" alt="BillTrack" />
          <ProjectIdentity />
        </div>
        <div style={{ height: 1, background: "#21262d", margin: "0 16px 12px" }} />
        <div className="sidebar-history" role="group" aria-label="Navigation history">
          <button type="button" className="btn-ghost" disabled={!canGoBack} onClick={onBack}>Back</button>
          <button type="button" className="btn-ghost" disabled={!canGoForward} onClick={onForward}>Forward</button>
        </div>
        <nav style={{ flex: 1, padding: "0 10px" }}>
          {navItems.filter(n => n.id !== 'drafts' || user.bill_email_copy_enabled !== false).map(n => (
            <button key={n.id} className="nav-link" aria-current={page === n.id ? "page" : undefined} onClick={() => onNavigate(n.id)}>
              <NavIcon name={n.id} /><span>{n.label}</span>
            </button>
          ))}
        </nav>
        <div style={{ padding: "16px 20px", borderTop: "1px solid #21262d" }}>
          <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>{user.username}</div>
          <button className="btn-ghost" style={{ width: "100%", padding: "6px" }} onClick={handleLogout}>Logout</button>
        </div>
      </aside>);
}

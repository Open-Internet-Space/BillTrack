
export function ToastNotification({toast,setToast}) {
return (toast && (
        <div role={toast.ok ? "status" : "alert"} style={{
          position: "fixed", bottom: 28, right: 28, maxWidth: "min(440px, calc(100vw - 56px))",
          background: toast.ok ? "#22c55e22" : "#ef444422",
          border: `1px solid ${toast.ok ? "#22c55e" : "#ef4444"}`,
          color: toast.ok ? "#22c55e" : "#f87171",
          padding: "12px 20px", borderRadius: 8, fontSize: 13,
          fontFamily: "'JetBrains Mono',monospace", zIndex: 9999
        }}>
          {toast.ok ? "✓" : "✗"} {toast.msg}
          {!toast.ok && <button type="button" className="error-dismiss" aria-label="Dismiss error" onClick={() => setToast(null)}>Dismiss</button>}
        </div>
      ));
}

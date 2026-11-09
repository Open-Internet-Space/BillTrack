export default function RefreshButton({ onRefresh, busy = false }) {
  return <button type="button" className="btn-ghost" onClick={onRefresh} disabled={busy || !onRefresh} style={{ padding: '8px 14px', fontSize: 12 }}>
    {busy ? 'Refreshing…' : '↻ Refresh'}
  </button>;
}

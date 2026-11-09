import { useEffect, useState } from "react";

export function usePagination(rows, resetKey) {
  const [pageSize, setPageSize] = useState(10);
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [resetKey]);
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * pageSize;
  return { pageSize, setPageSize, setPage, pageCount, currentPage, pageStart,
    total: rows.length, pageRows: rows.slice(pageStart, pageStart + pageSize) };
}

export default function Pagination({ pagination, label }) {
  const { pageSize, setPageSize, setPage, pageCount, currentPage, pageStart, total } = pagination;
  return <nav aria-label={`${label} pagination`} style={{ margin: "10px 0", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", fontSize: 12, color: "#8b949e", fontFamily: "'JetBrains Mono',monospace" }}>
    <span>Showing {total ? pageStart + 1 : 0}-{Math.min(pageStart + pageSize, total)} of {total} {label}</span>
    <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <span>Rows</span>
      <select aria-label="Rows per page" className="inp" style={{ width: 80, padding: "5px 8px", fontSize: 12 }} value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}>
        {[10, 15, 20, 25, 30].map(size => <option key={size} value={size}>{size}</option>)}
      </select>
      <button className="btn-ghost" style={{ padding: "5px 10px", fontSize: 12 }} disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Prev</button>
      <span>{currentPage}/{pageCount}</span>
      <button className="btn-ghost" style={{ padding: "5px 10px", fontSize: 12 }} disabled={currentPage === pageCount} onClick={() => setPage(currentPage + 1)}>Next</button>
    </span>
  </nav>;
}

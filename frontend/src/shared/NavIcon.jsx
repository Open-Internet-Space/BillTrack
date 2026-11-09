
export const navIconPaths = {
  dashboard: "M3 3h7v7H3z M14 3h7v4h-7z M14 11h7v10h-7z M3 14h7v7H3z",
  tenants: "M4 21V5l8-2 8 2v16 M2 21h20 M9 21v-5h6v5 M8 8h1 M15 8h1 M8 12h1 M15 12h1",
  bills: "M6 3h12v18l-3-2-3 2-3-2-3 2V3z M9 7h6 M9 11h6 M9 15h3",
  payments: "M3 5h18v14H3z M3 9h18 M7 14h3",
  adjustments: "M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-2 2 M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l2-2",
  penalty: "M12 3L2 21h20L12 3z M12 9v5 M12 17h.01",
  reports: "M5 3h10l4 4v14H5z M14 3v5h5 M9 12h6 M9 16h6",
};

export const NavIcon = ({ name }) => <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={navIconPaths[name]} /></svg>;
